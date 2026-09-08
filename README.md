# Design Notes

## Modules / Blocks

### Network Parser

- Input: 32-bit wide AXI stream at 312.5 MHz
- Parse MoldUDP64 protocol
- Check consecutivity of packet sequence numbers
- Small FIFO (handles minor recovery; size >> number of recovery cycles)

### Control Registers

- Error indicators: packet gap + first missing sequence number + length of missing sequence, fatal error, book invalid
- Input pins: force reset, write bypass, stock symbol to keep track of + enable, base offset for price index array

- Other: locate code / tracking number of desired stock symbol, populated after assignment message

### ITCH Parser

- Filter out a single stock given by locate code
- Irrelevant messages: wait number of cycles for message length

### Order book

- Order lookup: hash table (12 bit address, order ID[23:12] ^ ID[11:0] -> ID[63:0], Price[31:0], Shares[31:0])
- price indexing: 2048? price levels by control register input
- Best price: BBO N depth registers (Price[31:0], Volume[31:0])

### Output registers

- BBO, spread, sizes
- Book valid
- other?

# Design / Challenges

## Parser 4-byte alignement

Since the individual ITCH messages are consecutively packed within the payload of the MoldUDP64 packets, there is effectively only a minimum gap of 2 bytes of irrelevant ITCH data (from the message length fields in the MoldUDP64 protocol, if those are discarded). Furthermore, ITCH messages could have any byte lengths modulo 4.

Therefore, a 4-byte wide window that enters the pipeline in 1 cycle could contain relevant ITCH data from two different ITCH messages, massively complicating the logic needed to parse this naively.

### Solution 1

Instead, noticing that the 'tracking number' and 'timestamp' fields, present in all ITCH messages at byte positions [10:3], are not relevant information to this simplified design, we allow the network parser module to cut these two fields out, sending the beginning of the ITCH message 2 cycles later, without compromising latency.

Furthermore, to resolve the issue of byte offset, we keep a 12-byte sliding window of the stream to the ITCH parser, such that the relevant fields may be 4-to-1 MUX selected from the window based on the byte offset. Note that the 12-byte size also handles the issue of concatenating 8-byte fields such as order IDs from the 4-byte wide stream.

### Solution 2 (taken)

Another possible solution is to allow the message length fields of the MoldUDP64 packets to pass to the ITCH parser, allowing the ITCH parser to keep track of bytes left in the message, determining the beginning of the next message length field and ITCH message accordingly. To avoid needing to parse content from multiple messages in a cycle, we still employ the sliding window from solution 1 by delaying the processing of the first few bits of the second message for a cycle, but not delaying later bytes of the message for no impact on the latency. (2.1) Furthermore, enlarging the sliding window to cover the whole message allows for all fields to be extracted at once.

## L3 order book

Some kind of data structure is necessary to keep track of individual orders for fast lookup by order ID. During order execute, cancel, delete, and replace messages, the price and/or quantity of the order must be quickly accessible.

### Total capacity

A typical equity sees hundreds to thousands of resting orders (individual orders that must be tracked by the L3 book), and may spike to 10,000+ orders at certain times of the day (mega-cap). Thus, the total effective capacity of the L3 book for this project should be at least several thousand to handle all but the largest-cap stocks.

### Order ID hash collision

It is almost certain that multiple order IDs simultaneously exist in the book with the same hash. Therefore, taking inspiration from cache structure, we implement an 8-way, (N >= 2K)-set associative memory structure. Furthermore, we add a small content-addressable memory (CAM) to handle any overflows if more than 8 existing orders share the same hash. It was later determined that N = 2K was the maximum power of 2 meeting timing constraints.

Note that actually reaching the total 8N capacity given by this structure is nearly impossible because too many hash collisions would occur; using a Poisson model, the maximum safe load is approximately 5000 (expected overflow = 2.6 orders).

### Timing constraint / pipelining

Due to the high frequency required for this purpose, the selection logic for the large memory primitive macro (XPM_MEMORY_SDPRAM) itself has a 1-cycle read latency internally, followed by a custom 1 cycle latency for write-read bypassing and muxing from internal memory latches to the output. Then, the order ID comparison should be done the following cycle for a total L3 operation latency of 3. The order ID hash should be sent 2 cycles earlier from the ITCH decoder to facilitate pre-fetching of the hash table line.

## BBO extraction

For fast retrival of the top of the book, we store the top 2 aggregated price / shares orders in registers (note that storing the top 2 levels guarantees immediate output of the top price level after the order). The following algorithm outlines how to update these registers on a new order. WLOG, we consider only the bid / buy orders:

### Add order / Replace's add

Compare the price of the new add order against the existing top 2 bids. If a match exists, add the shares to the same entry. Otherwise, choose the slot of the highest bid lower the price of the newest order to insert a new entry in (shift lower prices down 1 register).

### Execute / Cancel / Delete order

Search for any matches in the existing top N bids. If a match exists, subtract the shares from the same entry. If the resulting number of shares is 0 (the price level has been depleted), shift the lower bids up 1 register, and send a request to the L2 price ladder to fetch the new 2nd best bid.

## L2 price table

A memory structure containing aggregate orders (total # of shares at each price) is necessary to faciliate fast retrieval of the next best buy/sell price when the best price is depleted; searching through all orders is too slow and introduces latency spikes. To facilitate the lookup itself, a wide register indicating whether any shares exist at each particular price level can determine the next best price via masking and priority encoding. The larger memory structure serves to update this register array. Because each order requires modifying the number of shares at a particular price, we require constant time access by price.

### Priority-Encoding existence array

Since we wish to determine the best level after an already-known level, we can take in the already-known level as an input and mask out all undesired existences. Then, we use a priority encoder to find the index of the best existence within the masked levels.

After some timing testing, it was determined that the masking + priority encoding needed to be split into two cycles; masking + encoding within smaller blocks, then encoding across blocks + address decoding for memory lookup.

### Latency / special cases

The minimum interval between possible depletions of the BBO is 4 idle cycles (exclusive) between the arrival of consecutive delete orders (which have the shortest length at 19 bytes (21 including message length field)). Therefore, to avoid needing to delay processing of any orders, the L2 search and BBO population must be completed in these 4 idle cycles to avoid complicating logic for updating the BBO.

Note that the next best price level must always be less than (buy-side)/greater than (sell-side) the worst price level existing in the BBO, so we continuously calculate the next best price level even before the BBO receives the order that would cause a depletion.

### Tick size

Prices sent over the ITCH protocol are expressed as 32 bit integers equal to 10^4 times the actual price, such that incrementing the price field corresponds to an increment of 0.01 cents. However, stocks priced above $1 share have a minimum increment of 1 cent/0.5 cents. It is more interesting/nuanced to design for a tick size of 0.5 cents (note that migrating to a tick size of 1 cent would be as simple as changing the price-ordering mapping, leading to a doubled price range, and should not impact timing).

Since it would cost an excessive amount of memory space to maintain tick sizes of 0.01 cents when at most only one slot every 50 ticks are actually used, we require a mapping of integers divisible by 50 to a continuous integer range (see address mapping below).

### Tick offset

Because most orders exist close to the top of the book +/- a few dollars, and orders outside this range are highly unlikely to require BBO access, a typical architecture would feature a sliding window that only captures the smaller range at the top of the book, and store the remaining L2 orders elsewhere (e.g. a CAM or directly iterating through the L3 table in the unlikely event the window needs to shift). To keep the maximum latency low and to keep this project in scope, we only implement a static window with a initializable tick offset provided by the test bench, and assert an error if the BBO moves outside of this range.

### Address mapping

As previously mentioned, for stocks priced above $1 per share, the tick size is 0.5 cents or 1 cent. To cover both of these cases, we design for a configuration with tick size of 0.5 cents. Then considering the tick offset, we require a bijective function to map the following sets: {OFFSET_BASE + 50 * k} -> {k} for integer k in [0, L2_SIZE - 1] (not necessarily in this order). This serves to calculate the address to access the L2 memory structure with.

**Option 1**: The obvious solution is to subtract OFFSET_BASE and divide by 50. Division by 50 (which is not a power of 2) would cost significant logic, and have a latency of around 1-2 cycles. Since the latency of the L2 book affects the latency during BBO depletions (the L2 register array must be updated to the same state as what the BBO received before a next best bid/offer lookup may occur), this option may be too expensive latency-wise, especially since no other work is possible to be done in parallel.

**Option 2** (taken): Directly divide by 2 and truncate the upper bits. For a L2 price ladder sized as a power of 2, 50/2 = 25 is coprime with the size, so the multiples of 25 in range cover all integers mod the size, although out of order. The benefit of this approach is that it costs 0 logic and only routing delay to calculate the address from the price.

However, the priority encoder to find the next best existing price will need take this different order into account. Since different OFFSET_BASE values mod L2_SIZE result in wildly different orderings of the address space, the best solution would still be to maintain the register array in order. Note that since the register array only needs to be written to as a result of a share count modification, which in turn requires a memory structure access, we may maintain a lookup table of the address space to the actual ordering at no cost to latency.

The reverse mappings of ordering to address space and price are necessary during a next best bid/offer lookup; the address space to access the aggregate shares at the selected price level, and the actual price to supply to the BBO module. While the calculation of price / address space from the ordering is simpler (a multiplication by 50 followed by adding the OFFSET_BASE), it was later determined that it could not fit into a single cycle in addition to address decoding for a memory primitive. Thus, we also maintain the reverse mapping of ordering to address space AND ordering to shares at the corresponding price in another memory structure to cut one cycle from the latency.
