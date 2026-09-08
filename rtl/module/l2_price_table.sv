`include "../include/definitions.sv"

module l2_price_table
    import definitions::*;
(
    input  logic        clk_i,
    input  logic        rst_ni,

    input  logic        init_v_i,
    input  logic [31:0] init_price_base_i,

    input  dec_book_s   l2_dec_book_i,

    // prefetching ordering of mask price addr
    // input  logic        prefetch_v_i,

    input  logic        bid_updt_req_i,
    input  l2_addr_t    bid_updt_price_addr_i,
    input  logic        off_updt_req_i,
    input  l2_addr_t    off_updt_price_addr_i,

    output bbo_word_s   bid_updt_o,
    output bbo_word_s   off_updt_o,

    output logic        l2_ready_o, // hold high

    output logic        l2_error_o
);

    typedef logic [L2_BLOCK_LOG_W-1:0] local_enc_t;

    logic initialized_q;
    logic [31:0] price_base_q, price_max_q; // inclusive

    dec_book_s dec_book_d, dec_book_q;

    logic                          exist_wea_d, exist_wen_q;
    l2_addr_t                      exist_waddr_d, exist_waddr_q;
    logic                          exist_din_d, exist_din_q;
    logic        [L2_MEM_SIZE-1:0] exist_arr_d, exist_arr_q;
    // 1: block encode, 2: global encode + lookup, 3: output (non-register)
    logic                          bid_updt_req_q, bid_updt_req_q2;
    l2_addr_t                      bid_updt_ordering;
    local_enc_t [L2_BLOCK_CNT-1:0] bid_local_enc_arr_d, bid_local_enc_arr_q;
    logic       [L2_BLOCK_CNT-1:0] bid_local_enc_arr_v_d, bid_local_enc_arr_v_q;
    l2_addr_t                      bid_enc_d, bid_enc_q;
    bbo_word_s                     bid_updt_d;

    logic                          off_updt_req_q, off_updt_req_q2;
    l2_addr_t                      off_updt_ordering;
    local_enc_t [L2_BLOCK_CNT-1:0] off_local_enc_arr_d, off_local_enc_arr_q;
    logic       [L2_BLOCK_CNT-1:0] off_local_enc_arr_v_d, off_local_enc_arr_v_q;
    l2_addr_t                      off_enc_d, off_enc_q;
    bbo_word_s                     off_updt_d;

    // both rams are written to with same data and enable
    logic        ram_wea;
    logic [63:0] ram_dina;

    l2_addr_t    pa_ram_addra;
    l2_addr_t    pa_ram_addrb;
    logic [63:0] pa_ram_doutb;
    logic        pa_ram_rst_done;
    l2_sdpram_wrapper pa_ram ( // indexed by price address (truncated bits of price)
        .clk_i,
        .rst_ni,
        .l2_ram_wea_i     (ram_wea),
        .l2_ram_addra_i   (pa_ram_addra),
        .l2_ram_dina_i    (ram_dina),
        .l2_ram_addrb_i   (pa_ram_addrb),
        .l2_ram_doutb_o   (pa_ram_doutb),
        .l2_ram_rst_done_o(pa_ram_rst_done)
    );

    l2_addr_t    od_ram_addra;
    l2_addr_t    od_ram_addrb;
    logic [63:0] od_ram_doutb;
    logic        od_ram_rst_done;
    l2_sdpram_wrapper od_ram ( // indexed by ordering (increasing price)
        .clk_i,
        .rst_ni,
        .l2_ram_wea_i     (ram_wea),
        .l2_ram_addra_i   (od_ram_addra),
        .l2_ram_dina_i    (ram_dina),
        .l2_ram_addrb_i   (od_ram_addrb),
        .l2_ram_doutb_o   (od_ram_doutb),
        .l2_ram_rst_done_o(od_ram_rst_done)
    );

    l2_addr_t    l2_lut_price_addr_1_in, l2_lut_ordering_1_out, l2_lut_price_addr_2_in, l2_lut_ordering_2_out;
    l2_addr_t    l2_lut_ordering_in;
    logic [31:0] l2_lut_price_out;
    logic        l2_lut_init_done;
    l2_ordering_lut l2_lut (
        .clk_i,
        .rst_ni,
        .init_v_i             (init_v_i),
        .init_price_base_i    (init_price_base_i),
        .l2_lut_price_addr_1_i(l2_lut_price_addr_1_in),
        .l2_lut_ordering_1_o  (l2_lut_ordering_1_out),
        .l2_lut_price_addr_2_i(l2_lut_price_addr_2_in),
        .l2_lut_ordering_2_o  (l2_lut_ordering_2_out),
        .l2_lut_ordering_i    (l2_lut_ordering_in),
        .l2_lut_price_o       (l2_lut_price_out),
        .l2_lut_init_done_o   (l2_lut_init_done)
    );

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            initialized_q       <= '0;

            dec_book_q.valid    <= '0;

            exist_wen_q         <= '0;
            exist_arr_q         <= '0;

            bid_updt_req_q      <= '0;
            bid_updt_req_q2     <= '0;

            off_updt_req_q      <= '0;
            off_updt_req_q2     <= '0;
        end else begin
            initialized_q       <= init_v_i || initialized_q;

            dec_book_q          <= dec_book_d;

            exist_wen_q         <= exist_wea_d;
            exist_arr_q         <= exist_arr_d;

            bid_updt_req_q      <= bid_updt_req_i;
            bid_updt_req_q2     <= bid_updt_req_q;

            off_updt_req_q      <= off_updt_req_i;
            off_updt_req_q2     <= off_updt_req_q;
        end
    end

    always_ff @(posedge clk_i) begin
        price_base_q            <= init_v_i ? init_price_base_i : price_base_q;
        price_max_q             <= init_v_i ? (init_price_base_i + (50 << L2_LOG_MEM_SIZE) - 50) : price_max_q;

        exist_waddr_q           <= exist_waddr_d;
        exist_din_q             <= exist_din_d;

        bid_updt_ordering       <= l2_lut_ordering_1_out;
        bid_local_enc_arr_q     <= bid_local_enc_arr_d;
        bid_local_enc_arr_v_q   <= bid_local_enc_arr_v_d;
        bid_enc_q               <= bid_enc_d;
        // bid_updt_o              <= bid_updt_d;

        off_updt_ordering       <= l2_lut_ordering_2_out;
        off_local_enc_arr_q     <= off_local_enc_arr_d;
        off_local_enc_arr_v_q   <= off_local_enc_arr_v_d;
        off_enc_q               <= off_enc_d;
        // off_updt_o              <= off_updt_d;
    end

    logic [63:0] order_new_shares;

    logic error_init, error_state, error_enum;
    logic error_tick;
    logic order_processing_error;
    always_comb begin : order_processing
        error_init  = '0;
        error_state = '0;
        error_enum  = '0;
        error_tick  = '0;

        // 0: lookup share count, lookup ordering index
        dec_book_d = l2_dec_book_i;

        if (l2_dec_book_i.valid) begin
            error_init = !initialized_q;

            // price in range and multiple of tick size
            // assert #0 (!dec_book_d.valid || dec_book_d.price % 50 == 0) else $error("order price not multiple of 0.5 cents");
            error_tick = l2_dec_book_i.price % 50 != 0;
            dec_book_d.valid = l2_dec_book_i.price >= price_base_q &&
                               l2_dec_book_i.price <= price_max_q;
        end

        // price_addr_ram lookup, price_addr to ordering lookup (other block)
        pa_ram_addrb = l2_dec_book_i.price[L2_LOG_MEM_SIZE:1];

        // 1: add/sub shares, write to mem
        exist_wea_d = '0;
        exist_din_d = '0;

        order_new_shares = pa_ram_doutb - {32'h0, dec_book_q.shares};
        if (dec_book_q.valid) begin
            unique case (dec_book_q.msg_type)
                MSG_ADD, MSG_REPLACE: begin
                    order_new_shares = pa_ram_doutb + {32'h0, dec_book_q.shares};
                    exist_wea_d = 1'b1;
                    exist_din_d = 1'b1;
                end
                MSG_REDUCE, MSG_DELETE: begin
                    order_new_shares = pa_ram_doutb - {32'h0, dec_book_q.shares};
                    assert #0 (exist_arr_q[l2_lut_ordering_1_out]) else $error("expected prior price existence");
                    exist_wea_d = 1'b1;
                    exist_din_d = order_new_shares > 0;
                end
                default: error_enum = 1'b1;
            endcase
        end

        // ram write
        ram_wea = dec_book_q.valid;
        pa_ram_addra = dec_book_q.price[L2_LOG_MEM_SIZE:1];
        od_ram_addra = l2_lut_ordering_1_out;
        ram_dina = order_new_shares;

        // exist_arr write prereg
        exist_waddr_d = l2_lut_ordering_1_out;

        // 2: write to exist_arr
        exist_arr_d = exist_arr_q;
        if (exist_wen_q) exist_arr_d[exist_waddr_q] = exist_din_q;

        order_processing_error = error_init | error_state | error_enum | error_tick;
    end

    always_comb begin : bid_updt
        bid_local_enc_arr_d = '0;
        bid_local_enc_arr_v_d = '0;

        // 0: local encode
        for (int b = 0; b < L2_BLOCK_CNT; b++) begin
            if (b[L2_BLOCK_LOG_CNT-1:0] < bid_updt_ordering[L2_LOG_MEM_SIZE-1:L2_BLOCK_LOG_W]) begin
                for (int i = L2_BLOCK_W - 1; i >= 0; i--) begin
                    if (exist_arr_q[(b << L2_BLOCK_LOG_W) + i]) begin
                        bid_local_enc_arr_d[b] = i[L2_BLOCK_LOG_W-1:0];
                        bid_local_enc_arr_v_d[b] = 1'b1;
                        break;
                    end
                end
            end else if (b[L2_BLOCK_LOG_CNT-1:0] == bid_updt_ordering[L2_LOG_MEM_SIZE-1:L2_BLOCK_LOG_W]) begin
                for (int i = L2_BLOCK_W - 1; i >= 0; i--) begin
                    if (exist_arr_q[(b << L2_BLOCK_LOG_W) + i]
                        && i < bid_updt_ordering[L2_BLOCK_LOG_W-1:0]) begin
                        bid_local_enc_arr_d[b] = i[L2_BLOCK_LOG_W-1:0];
                        bid_local_enc_arr_v_d[b] = 1'b1;
                        break;
                    end
                end
            end
        end

        // 1: global encode, lookup shares & price from ordering
        bid_enc_d = '0;
        for (int b = L2_BLOCK_CNT - 1; b >= 0; b--) begin
            if (bid_local_enc_arr_v_q[b]) begin
                bid_enc_d = {b[L2_BLOCK_LOG_CNT-1:0], bid_local_enc_arr_q[b]};
                break;
            end
        end

        // lookup handled in other block

        // output
        bid_updt_o = '{
            valid: bid_updt_req_q2,
            price: l2_lut_price_out,
            shares: od_ram_doutb
        };
    end

    always_comb begin : off_updt
        off_local_enc_arr_d = '0;
        off_local_enc_arr_v_d = '0;

        // local encode
        for (int b = 0; b < L2_BLOCK_CNT; b++) begin
            if (b[L2_BLOCK_LOG_CNT-1:0] > off_updt_ordering[L2_LOG_MEM_SIZE-1:L2_BLOCK_LOG_W]) begin
                for (int i = 0; i < L2_BLOCK_W; i++) begin
                    if (exist_arr_q[(b << L2_BLOCK_LOG_W) + i]) begin
                        off_local_enc_arr_d[b] = i[L2_BLOCK_LOG_W-1:0];
                        off_local_enc_arr_v_d[b] = 1'b1;
                        break;
                    end
                end
            end else if (b[L2_BLOCK_LOG_CNT-1:0] == off_updt_ordering[L2_LOG_MEM_SIZE-1:L2_BLOCK_LOG_W]) begin
                for (int i = 0; i < L2_BLOCK_W; i++) begin
                    if (exist_arr_q[(b << L2_BLOCK_LOG_W) + i]
                        && i > off_updt_ordering[L2_BLOCK_LOG_W-1:0]) begin
                        off_local_enc_arr_d[b] = i[L2_BLOCK_LOG_W-1:0];
                        off_local_enc_arr_v_d[b] = 1'b1;
                        break;
                    end
                end
            end
        end

        // global encode
        off_enc_d = '0;
        for (int b = 0; b < L2_BLOCK_CNT; b++) begin
            if (off_local_enc_arr_v_q[b]) begin
                off_enc_d = {b[L2_BLOCK_LOG_CNT-1:0], off_local_enc_arr_q[b]};
                break;
            end
        end

        // lookup handled in other block

        // output
        off_updt_o = '{
            valid: off_updt_req_q2,
            price: l2_lut_price_out,
            shares: od_ram_doutb
        };
    end

    always_comb begin : lut_price_to_ordering
        // read port 1 shared between order_processing and bid_updt
        l2_lut_price_addr_1_in = bid_updt_price_addr_i;
        if (l2_dec_book_i.valid) begin
            l2_lut_price_addr_1_in = l2_dec_book_i.price[L2_LOG_MEM_SIZE:1];
        end

        // read port 2 only for off_updt
        l2_lut_price_addr_2_in = off_updt_price_addr_i;
    end

    always_comb begin : updt_lookup
        od_ram_addrb = bid_enc_q;
        l2_lut_ordering_in = bid_enc_q;

        unique0 if (bid_updt_req_q) begin
            od_ram_addrb = bid_enc_q;
            l2_lut_ordering_in = bid_enc_q;
        end else if (off_updt_req_q) begin
            od_ram_addrb = off_enc_q;
            l2_lut_ordering_in = off_enc_q;
        end
    end

    assign l2_ready_o = pa_ram_rst_done && od_ram_rst_done && l2_lut_init_done;
    assign l2_error_o = order_processing_error;
endmodule


module l2_sdpram_wrapper
    // 1-stage pipelined write
    import definitions::*;
(
    input  logic        clk_i,
    input  logic        rst_ni,

    input  logic        l2_ram_wea_i,
    input  l2_addr_t    l2_ram_addra_i,
    input  logic [63:0] l2_ram_dina_i,

    input  l2_addr_t    l2_ram_addrb_i,
    output logic [63:0] l2_ram_doutb_o,

    output logic        l2_ram_rst_done_o // held high
);

    logic        wea, wea_q;
    l2_addr_t    addra, addra_q;
    logic [63:0] dina, dina_q;
    l2_addr_t    addrb, addrb_q;
    logic [63:0] pa_ram_doutb;

    // xpm_memory_sdpram: Simple Dual Port RAM
    // Xilinx Parameterized Macro, version 2026.1

`ifdef SYNTH
    xpm_memory_sdpram #(
        .ADDR_WIDTH_A(L2_LOG_MEM_SIZE),
        .ADDR_WIDTH_B(L2_LOG_MEM_SIZE),
        .AUTO_SLEEP_TIME(0),
        .BYTE_WRITE_WIDTH_A(64),
        .CASCADE_HEIGHT(1),
        .CLOCKING_MODE("common_clock"),
        .ECC_BIT_RANGE("7:0"),
        .ECC_MODE("no_ecc"),
        .ECC_TYPE("none"),
        .IGNORE_INIT_SYNTH(0),
        .MEMORY_INIT_FILE("none"),
        .MEMORY_INIT_PARAM("0"),
        .MEMORY_OPTIMIZATION("true"),
        .MEMORY_PRIMITIVE("auto"),
        .MEMORY_SIZE(64 << L2_LOG_MEM_SIZE),
        .MESSAGE_CONTROL(0),
        .RAM_DECOMP("auto"),
        .READ_DATA_WIDTH_B(64),
        .READ_LATENCY_B(1),
        .READ_RESET_VALUE_B("0"),
        .RST_MODE_A("SYNC"),
        .RST_MODE_B("SYNC"),
        .SIM_ASSERT_CHK(0),
        .USE_EMBEDDED_CONSTRAINT(0),
        .USE_MEM_INIT(1),
        .USE_MEM_INIT_MMI(0),
        .WAKEUP_TIME("disable_sleep"),
        .WRITE_DATA_WIDTH_A(64),
        .WRITE_MODE_B("no_change"),
        .WRITE_PROTECT(1)
    ) xpm_memory_sdpram_inst (
        .sleep(1'b0), // 1-bit input: sleep signal to enable the dynamic power saving feature.
        .clka(clk_i), // 1-bit input: Clock signal for port A. Also clocks port B when parameter CLOCKING_MODE is "common_clock".
        .ena(1'b1), // 1-bit input: Memory enable signal for port A. Must be high on the clock cycles when you initiate write
                                            // operations. Pipelined internally.

        .wea(wea), // WRITE_DATA_WIDTH_A/BYTE_WRITE_WIDTH_A-bit input: Write enable vector for port A input data port dina. 1 bit
                                            // wide for word-wide writes. In byte-wide write configurations, each bit controls the writing one byte of
                                            // dina to address addra. For example, to synchronously write only bits [15-8] of dina when WRITE_DATA_WIDTH_A
                                            // is 32, wea is 4'b0010.

        .addra(addra), // ADDR_WIDTH_A-bit input: Address for port A write operations.
        .dina(dina), // WRITE_DATA_WIDTH_A-bit input: Data input for port A write operations.
        .injectsbiterra(1'b0), // 1-bit input: Controls single bit error injection on input data when ECC enabled (Error injection capability
                                            // is not available in "decode_only" mode).

        .injectdbiterra(1'b0), // 1-bit input: Controls double bit error injection on input data when ECC enabled (Error injection capability
                                            // is not available in "decode_only" mode).

        .clkb(clk_i), // 1-bit input: Clock signal for port B when parameter CLOCKING_MODE is "independent_clock". Unused when
                                            // parameter CLOCKING_MODE is "common_clock".

        .rstb(1'b0), // 1-bit input: Reset signal for the final port B output register stage. Synchronously resets output port
                                            // doutb to the value specified by parameter READ_RESET_VALUE_B.

        .enb(1'b1), // 1-bit input: Memory enable signal for port B. Must be high on the clock cycles when you initiate read
                                            // operations. Pipelined internally.

        .regceb(1'b1), // 1-bit input: Clock Enable for the last register stage on the output data path.
        .addrb(addrb), // ADDR_WIDTH_B-bit input: Address for port B read operations.
        .doutb(pa_ram_doutb), // READ_DATA_WIDTH_B-bit output: Data output for port B read operations.
        .sbiterrb(), // 1-bit output: Status signal to indicate single bit error occurrence on the data output of port B.
        .dbiterrb() // 1-bit output: Status signal to indicate double bit error occurrence on the data output of port B.
    );
`else
    // simulation-only substitute
    xpm_memory_sdpram #(
        .ADDR_WIDTH_A(L2_LOG_MEM_SIZE),
        .WRITE_DATA_WIDTH_A(64),
        .ADDR_WIDTH_B(L2_LOG_MEM_SIZE),
        .READ_DATA_WIDTH_B(64)
    ) xpm_memory_spram_inst (
        .clka (clk_i),
        .wea  (wea),
        .addra(addra),
        .dina (dina),
        .addrb(addrb),
        .doutb(pa_ram_doutb)
    );
`endif

    // End of xpm_memory_sdpram_inst instantiation

    logic rst_in_progress_q;
    l2_addr_t count_q;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            rst_in_progress_q <= 1'b1;
            count_q <= {L2_LOG_MEM_SIZE{1'b1}};
            wea_q <= '0;
        end else begin
            rst_in_progress_q <= count_q != '0;
            count_q <= (rst_in_progress_q && count_q != 0) ? (count_q - L2_LOG_MEM_SIZE'(1)) : '0;
            wea_q <= l2_ram_wea_i;
        end
    end

    always_ff @(posedge clk_i) begin
        addra_q <= l2_ram_addra_i;
        addrb_q <= addrb;
        dina_q  <= l2_ram_dina_i;
    end

    always_comb begin
        wea     = rst_in_progress_q ? 1'b1 : l2_ram_wea_i;
        addra   = rst_in_progress_q ? count_q : l2_ram_addra_i;
        dina    = rst_in_progress_q ? '0 : l2_ram_dina_i;
        addrb   = l2_ram_addrb_i;

        // l2_ram_doutb_o = (addrb_q == addra_q) ? dina_q : pa_ram_doutb;
        l2_ram_doutb_o = pa_ram_doutb;

        l2_ram_rst_done_o = !rst_in_progress_q;
    end

endmodule

// L2_LOG_MEM_SIZE bit price address -> ordering conversion
// ordering -> 32 bit price conversion
module l2_ordering_lut
    import definitions::*;
(
    input  logic        clk_i,
    input  logic        rst_ni,

    input  logic        init_v_i,
    input  logic [31:0] init_price_base_i,
    // price addr -> ordering
    input  l2_addr_t    l2_lut_price_addr_1_i,
    output l2_addr_t    l2_lut_ordering_1_o,
    input  l2_addr_t    l2_lut_price_addr_2_i,
    output l2_addr_t    l2_lut_ordering_2_o,
    // ordering -> price
    input  l2_addr_t    l2_lut_ordering_i,
    output logic [31:0] l2_lut_price_o,

    output logic        l2_lut_init_done_o // held high
);

    logic     initialized_q; // init received
    logic     l2_lut_init_done_q; // init actually done
    l2_addr_t count_q;
    logic [31:0] price_q;

    logic     wea;
    l2_addr_t addra;



`ifdef SYNTH
    // xpm_memory_tdpram: True Dual Port RAM
    // Xilinx Parameterized Macro, version 2026.1

    xpm_memory_tdpram #(
        .ADDR_WIDTH_A(L2_LOG_MEM_SIZE),
        .ADDR_WIDTH_B(L2_LOG_MEM_SIZE),
        .AUTO_SLEEP_TIME(0),
        .BYTE_WRITE_WIDTH_A(L2_LOG_MEM_SIZE),
        .BYTE_WRITE_WIDTH_B(L2_LOG_MEM_SIZE),
        .CASCADE_HEIGHT(1),
        .CLOCKING_MODE("common_clock"),
        .ECC_BIT_RANGE("7:0"),
        .ECC_MODE("no_ecc"),
        .ECC_TYPE("none"),
        .IGNORE_INIT_SYNTH(0),
        .MEMORY_INIT_FILE("none"),
        .MEMORY_INIT_PARAM("0"),
        .MEMORY_OPTIMIZATION("true"),
        .MEMORY_PRIMITIVE("auto"),
        .MEMORY_SIZE(L2_LOG_MEM_SIZE << L2_LOG_MEM_SIZE),
        .MESSAGE_CONTROL(0),
        .RAM_DECOMP("auto"),
        .READ_DATA_WIDTH_A(L2_LOG_MEM_SIZE),
        .READ_DATA_WIDTH_B(L2_LOG_MEM_SIZE),
        .READ_LATENCY_A(1),
        .READ_LATENCY_B(1),
        .READ_RESET_VALUE_A("0"),
        .READ_RESET_VALUE_B("0"),
        .RST_MODE_A("SYNC"),
        .RST_MODE_B("SYNC"),
        .SIM_ASSERT_CHK(0),
        .USE_EMBEDDED_CONSTRAINT(0),
        .USE_MEM_INIT(1),
        .USE_MEM_INIT_MMI(0),
        .WAKEUP_TIME("disable_sleep"),
        .WRITE_DATA_WIDTH_A(L2_LOG_MEM_SIZE),
        .WRITE_DATA_WIDTH_B(L2_LOG_MEM_SIZE),
        .WRITE_MODE_A("no_change"),
        .WRITE_MODE_B("no_change"),
        .WRITE_PROTECT(1)
    ) price_addr_to_ordering (
        .sleep('0),
        .clka(clk_i),
        .rsta('0),
        .ena(1'b1),
        .regcea(1'b1),
        .wea(wea),
        .addra(addra),
        .dina(count_q),
        .injectsbiterra('0),
        .injectdbiterra('0),
        .douta(l2_lut_ordering_1_o),
        .sbiterra(),
        .dbiterra(),
        .clkb(clk_i),
        .rstb('0),
        .enb(1'b1),
        .regceb(1'b1),
        .web('0),
        .addrb(l2_lut_price_addr_2_i),
        .dinb('0),
        .injectsbiterrb('0),
        .injectdbiterrb('0),
        .doutb(l2_lut_ordering_2_o),
        .sbiterrb(),
        .dbiterrb()
    );

    // End of xpm_memory_tdpram_inst instantiation

    // xpm_memory_sdpram: Simple Dual Port RAM
    // Xilinx Parameterized Macro, version 2026.1
    xpm_memory_sdpram #(
        .ADDR_WIDTH_A(L2_LOG_MEM_SIZE),
        .ADDR_WIDTH_B(L2_LOG_MEM_SIZE),
        .AUTO_SLEEP_TIME(0),
        .BYTE_WRITE_WIDTH_A(32),
        .CASCADE_HEIGHT(1),
        .CLOCKING_MODE("common_clock"),
        .ECC_BIT_RANGE("7:0"),
        .ECC_MODE("no_ecc"),
        .ECC_TYPE("none"),
        .IGNORE_INIT_SYNTH(0),
        .MEMORY_INIT_FILE("none"),
        .MEMORY_INIT_PARAM("0"),
        .MEMORY_OPTIMIZATION("true"),
        .MEMORY_PRIMITIVE("auto"),
        .MEMORY_SIZE(32 << L2_LOG_MEM_SIZE),
        .MESSAGE_CONTROL(0),
        .RAM_DECOMP("auto"),
        .READ_DATA_WIDTH_B(32),
        .READ_LATENCY_B(1),
        .READ_RESET_VALUE_B("0"),
        .RST_MODE_A("SYNC"),
        .RST_MODE_B("SYNC"),
        .SIM_ASSERT_CHK(0),
        .USE_EMBEDDED_CONSTRAINT(0),
        .USE_MEM_INIT(1),
        .USE_MEM_INIT_MMI(0),
        .WAKEUP_TIME("disable_sleep"),
        .WRITE_DATA_WIDTH_A(32),
        .WRITE_MODE_B("no_change"),
        .WRITE_PROTECT(1)
    ) ordering_to_price (
        .sleep(1'b0),
        .clka(clk_i),
        .ena(1'b1),
        .wea(wea),
        .addra(count_q),
        .dina(price_q),
        .injectsbiterra(1'b0),
        .injectdbiterra(1'b0),
        .clkb(clk_i),
        .rstb(1'b0),
        .enb(1'b1),
        .regceb(1'b1),
        .addrb(l2_lut_ordering_i),
        .doutb(l2_lut_price_o),
        .sbiterrb(),
        .dbiterrb()
    );
`else
    // simulation-only substitute
    xpm_memory_tdpram #(
        .ADDR_WIDTH(L2_LOG_MEM_SIZE),
        .DATA_WIDTH(L2_LOG_MEM_SIZE)
    ) price_addr_to_ordering (
        .clk  (clk_i),
        .wea  (wea),
        .addra(addra),
        .dina (count_q),
        .douta(l2_lut_ordering_1_o),
        .web  ('0),
        .addrb(l2_lut_price_addr_2_i),
        .dinb ('0),
        .doutb(l2_lut_ordering_2_o)
    );

    xpm_memory_sdpram #(
        .ADDR_WIDTH_A(L2_LOG_MEM_SIZE),
        .WRITE_DATA_WIDTH_A(32),
        .ADDR_WIDTH_B(L2_LOG_MEM_SIZE),
        .READ_DATA_WIDTH_B(32)
    ) ordering_to_price (
        .clka (clk_i),
        .wea  (wea),
        .addra(count_q),
        .dina (price_q),
        .addrb(l2_lut_ordering_i),
        .doutb(l2_lut_price_o)
    );
`endif

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            initialized_q      <= '0;
            l2_lut_init_done_q <= '0;
        end else begin
            initialized_q      <= initialized_q || init_v_i;
            l2_lut_init_done_q <= l2_lut_init_done_q || (count_q == {L2_LOG_MEM_SIZE{1'b1}});
            count_q            <= init_v_i ? '0 : (count_q + L2_LOG_MEM_SIZE'(1));
            price_q            <= init_v_i ? init_price_base_i : price_q + 32'(50);
        end
    end

    always_comb begin
        wea = initialized_q && !l2_lut_init_done_q;
        addra = wea ? price_q[L2_LOG_MEM_SIZE:1] : l2_lut_price_addr_1_i;

        l2_lut_init_done_o = l2_lut_init_done_q;
    end

endmodule
