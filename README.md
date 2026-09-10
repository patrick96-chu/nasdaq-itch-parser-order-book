*For a complete architectural writeup, visit [my portfolio page](https://patrick96-chu.github.io/featured-projects/nasdaq-itch-order-book.html).*

# FPGA NASDAQ ITCH Parser + Order Book

## Overview

A SystemVerilog project designing an FPGA design to parse the NASDAQ ITCH 5.0 protocol and construct an order book to return the best bid and offers (aka "top of the book").

![Waveform](./assets/Waveform%202.png)

*Output BBO & Shares available 6 clocks after last word of incoming message/packet*

### Core Specs

| Metric / Parameter | Specification |
| :--- | :--- |
| **Target Device** | AMD/Xilinx Artix UltraScale+ (xcau25p-sfvb784-2e) |
| **Clock Frequency ($F_{\text{max}}$)** | **312.5 MHz** (3.2 ns clock period) |
| **Feed Protocols** | NASDAQ ITCH 5.0 (UDP) |
| **Ingress Bus Format** | 32-bit AXI4-Stream |
| **Tick-to-Signal Latency** | **6 Clock Cycles (19.2 ns)** |
| **L3 Order Book Capacity** | Hash Table: 2,048 Sets, 8 Ways (**16,384 slots**) |
| **L3 Collision Resolution** | 8-Entry Fully Associative Spillover CAM |
| **BBO Register Depth** | Depth-2 (Top-of-Book + Next Best) |
| **Verification Suite** | Cocotb (Python) & Automated Scoreboard |

### Problem Context & Hardware Motivation

In high-frequency trading (HFT), firms must process incoming market data and calculate orders to send back to the exchange's matching engine. Latency is critical here; a firm that has a shorter tick-to-trade latency is able to capture a better price / queue position. A traditional CPU-based approach processes sequentially through an OS stack, leading to latency spikes on cache misses, context switches, etc. Meanwhile, a hardware-based approach with FPGAs can process data in parallel and directly on the silicon, cutting down latency from microseconds/milliseconds to nanoseconds.

## Table of Contents
- [Stack](#stack)
- [System Architecture](#system-architecture)
- [Vivado Implementation](#vivado-implementation)
- [Directory Structure](#directory-structure)
- [Known Limitations & Design Tradeoffs](#known-limitations-&-design-tradeoffs)

## Stack

RTL: SystemVerilog<br>
Simulation: Verilator, Cocotb, GTKWave<br>
Timing Verification: Vivado<br>
Other: Python<br>

## System Architecture

![Block Diagram](./assets/Block%20Diagram%202.png)

### MoldUDP Parser
- Asserts correct session ID, sequence number, and packet/message length
    - This ensures there are no missing messages, adding an extra layer of safety

### ITCH Parser
- Asserts valid message type and alpha fields, correct message length for message type
- Decodes raw bytestream into structured buses of enums and values:
    - dec_ctrl_s for system-wide messages such as: System Event, Directory, Trading Action, Operational Halt
    - dec_book_s for stock-specific order messages such as: Add (with/without MPID), Execute (with/without price), Cancel, Delete, Replace (split into a Delete and an Add dec_book_s)
- Begins holding oid_hash output to upcoming dec_book's value 2 cycles before dec_book is valid to begin reading from L3's BRAM (read latency = 2)
- Also only allows dec_book valid if stock_locate matches (stock_locate supplied by Control module upon Directory message)

### Control
- Receives initialized stock_symbol and market_code from top level input
- Receives dec_ctrl_s from ITCH Parser
- Asserts System Event "Start of Messages" is first message received, consistent stock_locate with desired stock_symbol
- Outputs stock_locate corresponding to stock_symbol, stock_active if "Start of System hours" and stock is trading/in quotation period

### L3 Order Table
- Receives dec_book_s from ITCH Parser
- Maintains record of each individual order ID's shares, buy/sell side.
- Asserts share count and order IDs are consistent with previous messages (no negative shares, ID does not already exist on Add, ID exists on Reduce)
- Outputs lookup_dec_book, which has all necessary fields populated (e.g. shares to subtract in a Delete order)

### L2 Price Table
- Receives initialized price_base from top level input
- Receives lookup_dec_book from L3 Order Table
- Maintains record of shares at each price tick in a range
    - Maintains register of existence of shares at each price tick
    - This architecture is further discussed in the Tradeoffs & Design Choices section below
- Supplies BBO with next-best price level & shares upon depletion of a price level in the BBO

### BBO
- Receives lookup_dec_book from L3 Order Table
- Compares the new order against existing best 2 levels for 1-cycle determination of the best level immediately after new order
- Tracks number of total shares outside the best 2 levels to determine whether L2 can supply a valid next-best level

## Vivado Implementation

At 32 bits per clock, a clock of 3.2 ns = 312.5 MHz corresponds to 10Gb/s max throughput.

The final design met timing constraints:

![Timing Summary](./assets/Timing%20Summary%202.png)

*Post-implementation Timing Summary*


![Resource Utilization](./assets/Resource%20Utilization%202.png)

*Resource Utilization*

## Directory Structure

NASDAQ_ITCH_Parser/
├── rtl/
│   ├── include/        # .sv utilities directly part of the design itself<br>
│   ├── module/         # Sub-modules<br>
│   └── top.sv          # Top-level module<br>
├── sim/                # RTL design testing<br>
│   ├── data/           # Historical ITCH data\* & streamer<br>
│   ├── tests/          # Unit and integration test suites<br>
│   ├── utils/          # Helpers for writing test suites<br>
│   └── sim_runner.py   # Cocotb runner<br>
├── src/                # Python reference model<br>
│   ├── ref_model/      # Reference model modules<br>
│   ├── utils/          # Helpers for driving inputs to RTL and Python reference model<br>
├── tests/              # Python model unit and integration test suites and helpers<br>
└── README.md<br>

\*Data omitted due to large size; download from [https://emi.nasdaq.com/ITCH/].
## Known Limitations & Design Tradeoffs

### L3 Order Book Size

To keep the total pipeline latency at a minimum while maintaining a usuable amount of L3 memory size, the L3 memory is structured as a 8-way, 2048 set-associative hash table, with a small 8-entry content-addressable memory. This has a safe load of around 5000 orders, which is good for smaller large-cap stocks (meanwhile, mega-cap stocks see 10000+ resting orders).

Designing for compatability with mega-cap stocks would require adding one extra cycle for L3 memory reading.

### L2 Fixed Price Array Size

The L2 (aggregate shares) price table can only keep track of an approximately $10 range which must also be manually initialized. The $10 range comes from a limitation of the maximum number of ticks that can be sufficiently quickly priority-encoded to fulfill the BBO Register module's request for the next best price level. Note that basing the range on first received order would be inconsistent since order prices tend to be in a wider range at the beginning of the day.

An alternate approach to fix this limitation would be to implement a sliding-window table, but this sacrifices deterministic, small-constant latency when a shift is necessary. This would also require implementing FIFO buffers, further increasing latency.

### Dropped / Corrupted Packet Resolution

If network packets are dropped, the design currently simply asserts an error via checking the sequence number at the MoldUDP64 layer. To minimize the chances of dropping packets, multiple network receivers and parsers could be put together and the results be merged.

Mid-day recovery using GLIMPSE (which feeds only ADD orders needed to get the book to the specified state) can be added after the ITCH Message level, though it would require extra bypassing for the memory structures to handle a higher throughput.
