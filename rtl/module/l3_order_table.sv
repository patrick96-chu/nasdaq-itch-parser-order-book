`include "../include/definitions.sv"

module l3_order_table
    import definitions::*;
(
    input  logic        clk_i,
    input  logic        rst_ni,

    input  l3_addr_t    oid_hash_i,
    input  dec_book_s   l3_dec_book_i,

    output dec_book_s   lookup_dec_book_o,

    output logic        l3_ready_o, // held high

    output logic        l3_error_o
);

    logic       l3_ram_wea;
    l3_addr_t   l3_ram_addra;
    l3_line_t   l3_ram_line;
    line_idx_t  l3_ram_word_idx;
    l3_word_s   write_word;
    l3_line_t   l3_ram_doutb;
    l3_addr_t   l3_ram_addrb;
    l3_sdpram_wrapper l3_ram (
        .clk_i,
        .rst_ni,
        .l3_ram_wea_i       (l3_ram_wea),
        .l3_ram_addra_i     (l3_ram_addra),
        .l3_ram_line_i      (l3_ram_line),
        .l3_ram_word_idx_i  (l3_ram_word_idx),
        .l3_ram_write_word_i(write_word),
        .l3_ram_addrb_i     (l3_ram_addrb),
        .l3_ram_doutb_o     (l3_ram_doutb),
        .l3_ram_rst_done_o  (l3_ready_o)
    );

    logic        l3_cam_w_en;
    l3_word_s    l3_cam_d_in;
    l3_word_s    l3_cam_d_out; // cast output to l3_word_s
    logic [63:0] l3_cam_r_addr;
    logic [31:0] l3_cam_r_shares, l3_cam_sub_shares;
    logic        l3_cam_error;
    l3_cam_wrapper l3_cam (
        .clk_i,
        .rst_ni,
        .l3_cam_w_en_i      (l3_cam_w_en),
        .l3_cam_d_in_i      (write_word),
        .l3_cam_r_addr_i    (l3_cam_r_addr),
        .l3_cam_r_shares_i  (l3_cam_r_shares),
        .l3_cam_d_out_o     (l3_cam_d_out),
        .l3_cam_sub_shares_o(l3_cam_sub_shares),
        .l3_cam_error_o     (l3_cam_error)
    );

    l3_addr_t   oid_hash_q;
    dec_book_s  lookup_dec_book_d;

    logic       prev_is_buy_d, prev_is_buy_q;

    // always_ff @(posedge clk_i or negedge rst_ni) begin
    //     if (!rst_ni) begin
    //         oid_hash_v_q    <= '0;
    //     end else begin
    //         oid_hash_v_q    <= oid_hash_v_i;
    //     end
    // end

    always_ff @(posedge clk_i) begin
        oid_hash_q      <= oid_hash_i;
        prev_is_buy_q   <= prev_is_buy_d;
        lookup_dec_book_o <= lookup_dec_book_d;
    end

    logic       empty_hit;
    logic       match_hit;
    line_idx_t  empty_way;
    line_idx_t  match_way;
    l3_line_t   l3_ram_doutb_sub;

    logic is_buy;
    logic error_enum;
    logic error_add_id, error_reduce_id, error_neg_shares;
    always_comb begin
        error_enum          = '0;
        error_add_id        = '0;
        error_reduce_id     = '0;
        error_neg_shares    = '0;

        // ram default inputs
        l3_ram_wea          = '0;
        l3_ram_addra        = oid_hash_q;
        l3_ram_line         = l3_ram_doutb;
        l3_ram_word_idx     = '0;
        write_word          = '0;
        l3_ram_addrb        = oid_hash_i;

        // cam default inputs
        l3_cam_w_en         = '0;
        // l3_cam_d_in         = '0;
        l3_cam_r_addr       = l3_dec_book_i.order_id;
        l3_cam_r_shares     = l3_dec_book_i.shares;

        // parallel subtraction of shares for reduce op
        l3_ram_doutb_sub = l3_ram_doutb;
        for (int i = 0; i < (1 << L3_LOG_LINE_SIZE); i++) begin
            l3_ram_doutb_sub[i].shares = l3_ram_doutb[i].shares - l3_dec_book_i.shares;
        end

        // search ram line for matching OID
        empty_hit = '0;
        match_hit = '0;
        empty_way = '0;
        match_way = '0;
        for (int i = 0; i < (1 << L3_LOG_LINE_SIZE); i++) begin
            if (!l3_ram_doutb[i].valid) begin
                empty_hit = 1'b1;
                empty_way = i[L3_LOG_LINE_SIZE-1:0];
            end else if (l3_ram_doutb[i].order_id == l3_dec_book_i.order_id) begin
                assert #0 (!l3_dec_book_i.valid || !match_hit) else $error("multiple oid matches in ram line");
                match_hit = 1'b1;
                match_way = i[L3_LOG_LINE_SIZE-1:0];
            end
        end

        // cam result of oid search in l3_cam_d_out / l3_cam_sub_shares
        assert #0 (!l3_dec_book_i.valid || !l3_cam_d_out.valid || !match_hit) else $error("oid match found in both ram and cam");

        prev_is_buy_d = prev_is_buy_q;
        lookup_dec_book_d = l3_dec_book_i;
        is_buy = l3_dec_book_i.is_buy;
        if (l3_dec_book_i.valid) begin
            // resolve replace is_buy case
            if (l3_dec_book_i.msg_type == MSG_REPLACE) begin
                is_buy = prev_is_buy_q;
                lookup_dec_book_d.is_buy = prev_is_buy_q;
            end

            // add / replace op (assume book module populates buy/sell side)
            unique case (l3_dec_book_i.msg_type)
                MSG_ADD, MSG_REPLACE: begin
                    // assert #0 (!l3_cam_d_out.valid && !match_hit) else $error("unexpected oid match in ram or cam");
                    error_add_id = match_hit || l3_cam_d_out.valid;

                    write_word = '{
                        valid: 1'b1,
                        order_id: l3_dec_book_i.order_id,
                        is_buy: is_buy,
                        shares: l3_dec_book_i.shares,
                        price: l3_dec_book_i.price
                    };

                    if (empty_hit) begin
                        // write to ram
                        l3_ram_wea = 1'b1;
                        l3_ram_word_idx = empty_way;
                    end else begin
                        // write to cam
                        l3_cam_w_en = 1'b1;
                    end
                end
                MSG_REDUCE: begin
                    // assert #0 (l3_cam_d_out.valid || match_hit) else $error("expected oid match in ram or cam");
                    error_reduce_id = !(l3_cam_d_out.valid || match_hit);

                    write_word = '{
                        valid: 1'b1,
                        order_id: l3_dec_book_i.order_id,
                        is_buy: (match_hit ? l3_ram_doutb_sub[match_way].is_buy : l3_cam_d_out.is_buy),
                        shares: (match_hit ? l3_ram_doutb_sub[match_way].shares : l3_cam_sub_shares),
                        price: (match_hit ? l3_ram_doutb_sub[match_way].price : l3_cam_d_out.price)
                    };

                    if (write_word.shares == 0) write_word.valid = '0;

                    // slightly scuffed, assuming total shares never exceeds signed int range
                    error_neg_shares = write_word.shares[31] == 1'b1;

                    if (match_hit) begin
                        // write to ram
                        l3_ram_wea = 1'b1;
                        l3_ram_word_idx = match_way;
                    end else begin
                        // write to cam
                        l3_cam_w_en = 1'b1;
                    end

                    lookup_dec_book_d.is_buy = write_word.is_buy;
                    lookup_dec_book_d.price  = write_word.price;
                end

                MSG_DELETE: begin
                    // assert #0 (l3_cam_d_out.valid || match_hit) else $error("expected oid match in ram or cam");
                    error_reduce_id = !(l3_cam_d_out.valid || match_hit);

                    write_word = '0;
                    if (match_hit) begin
                        // write to ram
                        l3_ram_wea = 1'b1;
                        l3_ram_word_idx = match_way;
                    end else begin
                        // write to cam
                        l3_cam_w_en = 1'b1;
                    end

                    lookup_dec_book_d.is_buy = (match_hit ? l3_ram_doutb[match_way].is_buy : l3_cam_d_out.is_buy);
                    prev_is_buy_d = lookup_dec_book_d.is_buy;
                    lookup_dec_book_d.shares = (match_hit ? l3_ram_doutb[match_way].shares : l3_cam_sub_shares);
                    lookup_dec_book_d.price  = (match_hit ? l3_ram_doutb[match_way].price : l3_cam_d_out.price);
                end
                default: error_enum = 1'b1;
            endcase
        end

        // lookup_dec_book_o = lookup_dec_book_d;
        l3_error_o = error_enum |
                     error_add_id | error_reduce_id | error_neg_shares | l3_cam_error;
    end

endmodule

module l3_cam_synth_test
    // only for timing testing (adds register to output)
    import definitions::*;
(
    input   logic       clk_i,
    input   logic       rst_ni,

    input   logic       l3_cam_w_en_i,
    input   l3_word_s   l3_cam_d_in_i,

    input   logic[63:0] l3_cam_r_addr_i,
    input   logic[31:0] l3_cam_r_shares_i, // do parallel subtraction of shares

    output  logic       l3_cam_d_out_xor_o,
    output  logic       l3_cam_sub_shares_xor_o, // result of selecting from parallel subtraction

    output  logic       l3_cam_error_o
);

    l3_word_s   l3_cam_d_out_d, l3_cam_d_out_q;
    logic[31:0] l3_cam_sub_shares_d, l3_cam_sub_shares_q;
    l3_cam_wrapper l3_cam (
        .clk_i,
        .rst_ni,
        .l3_cam_w_en_i      (l3_cam_w_en_i),
        .l3_cam_d_in_i      (l3_cam_d_in_i),
        .l3_cam_r_addr_i    (l3_cam_r_addr_i),
        .l3_cam_r_shares_i  (l3_cam_r_shares_i),
        .l3_cam_d_out_o     (l3_cam_d_out_d),
        .l3_cam_sub_shares_o(l3_cam_sub_shares_d),
        .l3_cam_error_o     (l3_cam_error_o)
    );

    always_ff @(posedge clk_i) begin
        l3_cam_d_out_q <= l3_cam_d_out_d;
        l3_cam_sub_shares_q <= l3_cam_sub_shares_d;
    end

    assign l3_cam_d_out_xor_o = ^l3_cam_d_out_q;
    assign l3_cam_sub_shares_xor_o = ^l3_cam_sub_shares_q;
endmodule


module l3_cam_wrapper
    // combinational read, 1-stage pipelined write (read available 2 clock edges after)
    import definitions::*;
(
    input   logic       clk_i,
    input   logic       rst_ni,

    input   logic       l3_cam_w_en_i,
    input   l3_word_s   l3_cam_d_in_i,

    input   logic[63:0] l3_cam_r_addr_i,
    input   logic[31:0] l3_cam_r_shares_i, // do parallel subtraction of shares

    output  l3_word_s   l3_cam_d_out_o,
    output  logic[31:0] l3_cam_sub_shares_o, // result of selecting from parallel subtraction

    output  logic       l3_cam_error_o
);
    logic     l3_cam_w_en_q;
    l3_word_s l3_cam_d_in_q;

    // use l3_word_s.valid as data valid
    l3_word_s[L3_CAM_SIZE - 1:0] mem_arr_q, mem_arr_d;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            l3_cam_w_en_q <= '0;
            for (int i = 0; i < L3_CAM_SIZE; i++) begin
                mem_arr_q[i].valid <= '0;
            end
        end else begin
            l3_cam_w_en_q <= l3_cam_w_en_i;

            mem_arr_q <= mem_arr_d;
        end
    end

    always_ff @(posedge clk_i) begin
        l3_cam_d_in_q <= l3_cam_d_in_i;
    end

    logic [L3_LOG_CAM_SIZE - 1:0] empty_slot;
    logic empty_hit, write_hit, lookup_hit;

    always_comb begin
        mem_arr_d = mem_arr_q;

        empty_slot = '0;
        empty_hit = '0;
        write_hit = '0;

        l3_cam_d_out_o = '0; // default invalid dout
        l3_cam_sub_shares_o = '0;
        l3_cam_error_o = '0;

        // write
        if (l3_cam_w_en_q) begin
            for (int i = 0; i < L3_CAM_SIZE; i++) begin
                if (mem_arr_q[i].order_id == l3_cam_d_in_q.order_id) begin
                    // use same slot
                    mem_arr_d[i] = l3_cam_d_in_q;
                    write_hit = 1'b1;
                end

                if (!mem_arr_q[i].valid) begin
                    empty_slot = i[L3_LOG_CAM_SIZE - 1:0];
                    empty_hit = 1'b1;
                end
            end

            if (!write_hit) begin
                if (!empty_hit) begin
                    // CAM full
                    l3_cam_error_o = 1'b1;
                end else begin
                    mem_arr_d[empty_slot] = l3_cam_d_in_q;
                end
            end
        end

        // read
        lookup_hit = '0;
        // bypass from write
        // if (l3_cam_r_addr_i == l3_cam_d_in_q.order_id) begin
        //     l3_cam_d_out_o = l3_cam_d_in_q;
        //     l3_cam_sub_shares_o = l3_cam_d_in_q.shares - l3_cam_r_shares_i;
        // end else begin
        for (int i = 0; i < L3_CAM_SIZE; i++) begin
            if (mem_arr_q[i].order_id == l3_cam_r_addr_i && mem_arr_q[i].valid) begin
                assert #0 (!lookup_hit) else $error("multiple oid matches found in cam");
                lookup_hit = 1'b1;
                l3_cam_d_out_o = mem_arr_q[i];
                l3_cam_sub_shares_o = mem_arr_q[i].shares - l3_cam_r_shares_i;
            end
        end
        // end
    end

endmodule


module l3_sdpram_wrapper
    // read latency 2 (2nd cycle for bypass path + selection from memory)
    // write by specifying addr, write word, and index within line.
    import definitions::*;
(
    input   logic       clk_i,
    input   logic       rst_ni,

    input   logic       l3_ram_wea_i,
    input   l3_addr_t   l3_ram_addra_i,
    input   l3_line_t   l3_ram_line_i,
    input   line_idx_t  l3_ram_word_idx_i,
    input   l3_word_s   l3_ram_write_word_i,

    input   l3_addr_t   l3_ram_addrb_i,
    output  l3_line_t   l3_ram_doutb_o,

    output  logic       l3_ram_rst_done_o // held high
);

    logic      wea, wea_q, wea_q2;
    l3_addr_t  addra, addra_q, addra_q2;
    l3_line_t  line_q, dina_mod, dina, dina_q;
    line_idx_t word_idx_q;
    l3_word_s  word_q;

    l3_addr_t  addrb, addrb_q;
    l3_line_t  l3_ram_doutb, l3_ram_doutb_d;

    // xpm_memory_sdpram: Simple Dual Port RAM
    // Xilinx Parameterized Macro, version 2026.1

`ifdef SYNTH
    xpm_memory_sdpram #(
        .ADDR_WIDTH_A(L3_LOG_ADDR_SIZE),
        .ADDR_WIDTH_B(L3_LOG_ADDR_SIZE),
        .AUTO_SLEEP_TIME(0),
        .BYTE_WRITE_WIDTH_A(L3_WORD_SIZE << L3_LOG_LINE_SIZE),
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
        .MEMORY_SIZE(L3_WORD_SIZE << L3_LOG_MEM_SIZE),
        .MESSAGE_CONTROL(0),
        .RAM_DECOMP("auto"),
        .READ_DATA_WIDTH_B(L3_WORD_SIZE << L3_LOG_LINE_SIZE),
        .READ_LATENCY_B(1),
        .READ_RESET_VALUE_B("0"),
        .RST_MODE_A("SYNC"),
        .RST_MODE_B("SYNC"),
        .SIM_ASSERT_CHK(0),
        .USE_EMBEDDED_CONSTRAINT(0),
        .USE_MEM_INIT(1),
        .USE_MEM_INIT_MMI(0),
        .WAKEUP_TIME("disable_sleep"),
        .WRITE_DATA_WIDTH_A(L3_WORD_SIZE << L3_LOG_LINE_SIZE),
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
        .doutb(l3_ram_doutb), // READ_DATA_WIDTH_B-bit output: Data output for port B read operations.
        .sbiterrb(), // 1-bit output: Status signal to indicate single bit error occurrence on the data output of port B.
        .dbiterrb() // 1-bit output: Status signal to indicate double bit error occurrence on the data output of port B.
    );
`else
    // simulation-only substitute
    xpm_memory_sdpram #(
        .ADDR_WIDTH_A(L3_LOG_ADDR_SIZE),
        .WRITE_DATA_WIDTH_A(L3_WORD_SIZE << L3_LOG_LINE_SIZE),
        .ADDR_WIDTH_B(L3_LOG_ADDR_SIZE),
        .READ_DATA_WIDTH_B(L3_WORD_SIZE << L3_LOG_LINE_SIZE)
    ) xpm_memory_spram_inst (
        .clka(clk_i),
        .wea(wea),
        .addra(addra),
        .dina(dina),
        .addrb(addrb),
        .doutb(l3_ram_doutb)
    );
`endif

    // End of xpm_memory_sdpram_inst instantiation

    logic rst_in_progress_q;
    l3_addr_t count_q;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            rst_in_progress_q <= 1'b1;
            count_q <= {L3_LOG_ADDR_SIZE{1'b1}};
            wea_q <= '0;
        end else begin
            rst_in_progress_q <= count_q != '0;
            count_q <= (rst_in_progress_q && count_q != 0) ? (count_q - L3_LOG_ADDR_SIZE'(1)) : '0;
            wea_q <= l3_ram_wea_i;
        end
    end

    always_ff @(posedge clk_i) begin
        addra_q     <= l3_ram_addra_i;
        line_q      <= l3_ram_line_i;
        word_idx_q  <= l3_ram_word_idx_i;
        word_q      <= l3_ram_write_word_i;

        addrb_q     <= addrb;
        wea_q2      <= wea_q;
        addra_q2    <= addra_q;
        dina_q      <= dina;

        l3_ram_doutb_o <= l3_ram_doutb_d;
    end

    always_comb begin
        // insert word into line
        dina_mod = line_q;
        dina_mod[word_idx_q] = word_q;

        // memory module inputs
        wea     = rst_in_progress_q ? 1'b1 : wea_q;
        addra   = rst_in_progress_q ? count_q : addra_q;
        dina    = rst_in_progress_q ? '0 : dina_mod;
        addrb   = l3_ram_addrb_i;

        // 2nd read cycle + bypass
        l3_ram_doutb_d = l3_ram_doutb;
        if (addrb_q == addra_q2 && wea_q2) begin
            l3_ram_doutb_d = dina_q;
        end

        l3_ram_rst_done_o = !rst_in_progress_q;
    end

endmodule
