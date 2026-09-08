`include "../include/definitions.sv"

module bbo
    import definitions::*;
(
    input  logic        clk_i,
    input  logic        rst_ni,

    input  logic        init_v_i,
    input  logic [31:0] init_price_base_i,

    input  dec_book_s   bbo_dec_book_i,

    input  bbo_word_s   bid_updt_i,
    input  bbo_word_s   off_updt_i,

    output bbo_s        bbo_res_o,

    // non-reg output (already reg in bbo_half)
    output logic        bid_updt_req_o,
    output l2_addr_t    bid_updt_price_addr_o,
    output logic        off_updt_req_o,
    output l2_addr_t    off_updt_price_addr_o,

    output logic        bbo_error_o
);

    logic [31:0] bid_init_price_bound;
    dec_book_s   bid_dec_book;
    bbo_word_s   bid_res;
    logic        bid_half_error;
    bbo_half #(
        .IS_BUY(1)
    ) bid_half (
        .clk_i,
        .rst_ni,
        .init_v_i          (init_v_i),
        .init_price_bound_i(bid_init_price_bound),
        .half_dec_book_i   (bid_dec_book),
        .updt_i            (bid_updt_i),
        .half_res_o        (bid_res),
        .updt_req_o        (bid_updt_req_o),
        .updt_price_addr_o (bid_updt_price_addr_o),
        .half_error_o      (bid_half_error)
    );

    logic [31:0] off_init_price_bound;
    dec_book_s   off_dec_book;
    bbo_word_s   off_res;
    logic        off_half_error;
    bbo_half #(
        .IS_BUY(0)
    ) off_half (
        .clk_i,
        .rst_ni,
        .init_v_i          (init_v_i),
        .init_price_bound_i(off_init_price_bound),
        .half_dec_book_i   (off_dec_book),
        .updt_i            (off_updt_i),
        .half_res_o        (off_res),
        .updt_req_o        (off_updt_req_o),
        .updt_price_addr_o (off_updt_price_addr_o),
        .half_error_o      (off_half_error)
    );

    // logic [63:0] bbo_spread_q;

    // always_ff @(posedge clk_i or negedge rst_ni) begin
    //     if (!rst_ni) begin
    //         bbo_res_o.bid_valid <= '0;
    //         bbo_res_o.off_valid <= '0;
    //     end
    // end

    // always_ff @(posedge clk_i) begin
    //     bbo_spread_q <= off_res.price - bid_res.price;
    // end

    logic is_bid, is_off;
    always_comb begin
        bid_init_price_bound = init_price_base_i;
        off_init_price_bound = init_price_base_i + 50 * (L2_MEM_SIZE - 1);

        is_bid = bbo_dec_book_i.valid && bbo_dec_book_i.is_buy;
        is_off = bbo_dec_book_i.valid && !bbo_dec_book_i.is_buy;
        bid_dec_book = bbo_dec_book_i;
        off_dec_book = bbo_dec_book_i;
        bid_dec_book.valid = is_bid;
        off_dec_book.valid = is_off;

        // rest of valid condition in book module (stock_active)
        bbo_res_o = '{
            bid_valid: bid_res.valid,
            bid_price: bid_res.price,
            bid_shares: bid_res.shares,
            off_valid: off_res.valid,
            off_price:off_res.price,
            off_shares: off_res.shares,
            spread: off_res.price - bid_res.price
        };

        bbo_error_o = bid_half_error || off_half_error;
    end

endmodule

// module bbo_half
//     import definitions::*;
// #(
//     parameter bit IS_BUY
// ) (
//     input  logic        clk_i,
//     input  logic        rst_ni,

//     input  logic        init_v_i,
//     input  logic [31:0] init_price_bound_i,

//     input  dec_book_s   half_dec_book_i,

//     input  bbo_word_s   updt_i,

//     output bbo_word_s   half_res_o,

//     output logic        updt_req_o,
//     output l2_addr_t    updt_price_addr_o,

//     output logic        half_error_o
// );
//     logic        initialized_q;
//     logic [31:0] price_bound_q;

//     // lower indices closer to top of book
//     // arr[BBO_DEPTH] is '0 to cleanly handle index overflow / depletion
//     bbo_word_s         [BBO_DEPTH:0] arr_q, arr_d;
//     logic [63:0]                     arr_mod [BBO_DEPTH - 1:0];
//     bbo_arr_chng_e [BBO_DEPTH - 1:0] arr_chng;
//     bbo_word_s word_ins;
//     logic ins_flag, del_flag, mod_flag, out_flag;
//     logic [63:0] out_size_all_q, out_size_all_d, out_size_in_range_q, out_size_in_range_d; // total shares outside bbo
//     logic updt_able_all_q, updt_able_in_range_q, updt_ing_q, updt_ing_d, updt_req_d;

//     // logic [31:0] lowest_price_q, lowest_price_d;

//     // logic [31:0] updt_mask_enc_d;

//     always_ff @(posedge clk_i or negedge rst_ni) begin
//         if (!rst_ni) begin
//             initialized_q           <= '0;

//             arr_q                   <= '0;

//             out_size_all_q          <= '0;
//             out_size_in_range_q     <= '0;
//             updt_able_all_q         <= '0;
//             updt_able_in_range_q    <= '0;
//             updt_ing_q              <= '0;

//             updt_req_o              <= '0;
//         end else begin
//             initialized_q           <= init_v_i || initialized_q;

//             arr_q                   <= arr_d;

//             out_size_all_q          <= out_size_all_d;
//             out_size_in_range_q     <= out_size_in_range_d;
//             updt_able_all_q         <= out_size_all_q > '0;
//             updt_able_in_range_q    <= out_size_in_range_q  > '0;
//             updt_ing_q              <= updt_ing_d;

//             // lowest_price_q          <= lowest_price_d;
//             updt_req_o              <= updt_req_d;
//         end
//     end

//     always_ff @(posedge clk_i) begin
//         price_bound_q <= init_v_i ? init_price_bound_i : price_bound_q;
//         // updt_price_addr_o <= updt_mask_enc_d;
//     end

//     logic is_add, in_range;

//     logic error_state, error_init, error_enum;
//     logic error_updt;
//     always_comb begin
//         error_state = '0;
//         error_init  = '0;
//         error_enum  = '0;
//         error_updt  = '0;

//         arr_d       = arr_q;
//         for (int i = 0; i < BBO_DEPTH; i++) arr_mod[i] = arr_q[i].shares;
//         arr_chng    = {BBO_DEPTH{HOLD}};
//         word_ins    = '{valid: half_dec_book_i.valid, price: half_dec_book_i.price, shares: {32'b0, half_dec_book_i.shares}};
//         ins_flag    = '0;
//         del_flag    = '0;
//         mod_flag    = '0;
//         out_flag    = 1'b1;

//         // lowest_price_d      = arr_q[BBO_DEPTH - 1];
//         updt_price_addr_o = arr_q[BBO_DEPTH - 1].price[L2_LOG_MEM_SIZE:1];

//         out_size_all_d      = out_size_all_q;
//         out_size_in_range_d = out_size_in_range_q;
//         updt_req_d          = '0;
//         updt_ing_d          = updt_ing_q;

//         is_add = (half_dec_book_i.msg_type == MSG_ADD || half_dec_book_i.msg_type == MSG_REPLACE);
//         in_range = '0;

//         if (updt_i.valid) begin
//             error_state = !updt_ing_q || half_dec_book_i.valid;
//             error_init = !initialized_q;
//             // assert #0 (updt_ing_q) else $error("unexpected updt");

//             updt_price_addr_o = updt_i.price[L2_LOG_MEM_SIZE:1];

//             arr_d[BBO_DEPTH - 1] = updt_i;
//             out_size_all_d = out_size_all_q - updt_i.shares;
//             out_size_in_range_d = out_size_in_range_q - updt_i.shares;
//             updt_ing_d = '0;
//         end

//         if (half_dec_book_i.valid) begin
//             error_state = updt_ing_q;
//             error_init = !initialized_q;
//             // assert #0 (!updt_ing_q) else $error("unexpected order input while waiting for updt");

//             for (int i = 0; i < BBO_DEPTH; i++) begin
//                 arr_mod[i] = is_add ?
//                     arr_q[i].shares + {32'b0, half_dec_book_i.shares} :
//                     arr_q[i].shares - {32'b0, half_dec_book_i.shares};

//                 if (ins_flag) begin
//                     arr_chng[i] = TOP;
//                 end else if (del_flag) begin
//                     arr_chng[i] = BOTTOM;
//                 end else if (mod_flag) begin
//                     arr_chng[i] = HOLD;
//                 end else if (!arr_q[i].valid ||
//                             (IS_BUY && arr_q[i].price < half_dec_book_i.price) ||
//                             (!IS_BUY && arr_q[i].price > half_dec_book_i.price)) begin
//                     arr_chng[i] = INSERT;
//                     out_flag = '0;
//                     ins_flag = 1'b1;
//                 end else if (arr_q[i].price == half_dec_book_i.price) begin
//                     unique if (arr_mod[i] == '0) begin
//                         // price level depletion
//                         arr_chng[i] = BOTTOM;
//                         del_flag = 1'b1;
//                     end else if (arr_mod[i] > '0) begin
//                         arr_chng[i] = MODIFY;
//                         mod_flag = 1'b1;
//                     end
//                     out_flag = '0;
//                 end else begin
//                     arr_chng[i] = HOLD;
//                 end

//                 unique case (arr_chng[i])
//                     HOLD:    arr_d[i] = arr_q[i];
//                     MODIFY:  arr_d[i].shares = arr_mod[i];
//                     TOP:     arr_d[i] = arr_q[i - 1];
//                     BOTTOM:  arr_d[i] = arr_q[i + 1];
//                     INSERT:  arr_d[i] = word_ins;
//                     default: error_enum = 1;
//                 endcase
//             end

//             unique if (ins_flag) begin
//                 // BBO_DEPTHth top price evicted from BBO
//                 out_size_all_d = out_size_all_q + arr_q[BBO_DEPTH - 1].shares;
//                 in_range = (IS_BUY && arr_q[BBO_DEPTH - 1].price >= price_bound_q) ||
//                    (!IS_BUY && arr_q[BBO_DEPTH - 1].price <= price_bound_q);
//                 out_size_in_range_d = in_range ? (out_size_in_range_q + arr_q[BBO_DEPTH - 1].shares) : out_size_in_range_q;
//             end else if (del_flag) begin
//                 updt_req_d = updt_able_all_q && updt_able_in_range_q;
//                 updt_ing_d = updt_req_d;
//                 error_updt = updt_able_all_q && !updt_able_in_range_q;
//             end else if (out_flag) begin
//                 // price past top BBO_DEPTH price levels
//                 out_size_all_d = is_add ?
//                                  (out_size_all_q + {32'b0, half_dec_book_i.shares}) :
//                                  (out_size_all_q - {32'b0, half_dec_book_i.shares});

//                 in_range = (IS_BUY && half_dec_book_i.price >= price_bound_q) ||
//                         (!IS_BUY && half_dec_book_i.price <= price_bound_q);

//                 out_size_in_range_d = in_range ? (is_add ?
//                                       (out_size_in_range_q + {32'b0, half_dec_book_i.shares}) :
//                                       (out_size_in_range_q - {32'b0, half_dec_book_i.shares})) :
//                                       out_size_in_range_q;
//             end
//         end

//         half_res_o = arr_q[0];

//         half_error_o = error_state | error_init | error_enum | error_updt;
//     end

// endmodule

// non-parameterized, more hardcoded (less extraneous signals, reduce fanout)
module bbo_half
    import definitions::*;
#(
    parameter bit IS_BUY
) (
    input  logic        clk_i,
    input  logic        rst_ni,

    input  logic        init_v_i,
    input  logic [31:0] init_price_bound_i,

    input  dec_book_s   half_dec_book_i,

    input  bbo_word_s   updt_i,

    output bbo_word_s   half_res_o,

    output logic        updt_req_o,
    output l2_addr_t    updt_price_addr_o,

    output logic        half_error_o
);
    logic        initialized_q;
    logic [31:0] price_bound_q;

    // lower indices closer to top of book
    // arr[BBO_DEPTH] is '0 to cleanly handle index overflow / depletion
    bbo_word_s     [1:0] arr_q, arr_d;
    logic [63:0]         arr_mod [1:0];
    bbo_arr_chng_e [1:0] arr_chng;
    bbo_word_s word_ins;
    logic ins_flag, del_flag, mod_flag, out_flag;
    logic [63:0] out_size_all_q, out_size_all_d, out_size_in_range_q, out_size_in_range_d; // total shares outside bbo
    logic updt_able_all_q, updt_able_in_range_q, updt_ing_q, updt_ing_d, updt_req_d;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            initialized_q           <= '0;

            arr_q                   <= '0;

            out_size_all_q          <= '0;
            out_size_in_range_q     <= '0;
            updt_able_all_q         <= '0;
            updt_able_in_range_q    <= '0;
            updt_ing_q              <= '0;

            updt_req_o              <= '0;
        end else begin
            initialized_q           <= init_v_i || initialized_q;

            arr_q                   <= arr_d;

            out_size_all_q          <= out_size_all_d;
            out_size_in_range_q     <= out_size_in_range_d;
            updt_able_all_q         <= out_size_all_q > '0;
            updt_able_in_range_q    <= out_size_in_range_q  > '0;
            updt_ing_q              <= updt_ing_d;

            // lowest_price_q          <= lowest_price_d;
            updt_req_o              <= updt_req_d;
        end
    end

    always_ff @(posedge clk_i) begin
        price_bound_q <= init_v_i ? init_price_bound_i : price_bound_q;
        // updt_price_addr_o <= updt_mask_enc_d;
    end

    logic is_add, in_range;

    logic error_state, error_init, error_enum;
    logic error_updt;
    always_comb begin
        error_state = '0;
        error_init  = '0;
        error_enum  = '0;
        error_updt  = '0;

        arr_d       = arr_q;
        for (int i = 0; i < 2; i++) arr_mod[i] = arr_q[i].shares;
        arr_chng    = {2{HOLD}};
        word_ins    = '{valid: half_dec_book_i.valid, price: half_dec_book_i.price, shares: {32'b0, half_dec_book_i.shares}};
        ins_flag    = '0;
        del_flag    = '0;
        mod_flag    = '0;
        out_flag    = 1'b1;

        updt_price_addr_o = arr_q[1].price[L2_LOG_MEM_SIZE:1];

        out_size_all_d      = out_size_all_q;
        out_size_in_range_d = out_size_in_range_q;
        updt_req_d          = '0;
        updt_ing_d          = updt_ing_q;

        is_add = (half_dec_book_i.msg_type == MSG_ADD || half_dec_book_i.msg_type == MSG_REPLACE);
        in_range = '0;

        if (updt_i.valid) begin
            error_state = !updt_ing_q || half_dec_book_i.valid;
            error_init = !initialized_q;
            // assert #0 (updt_ing_q) else $error("unexpected updt");

            updt_price_addr_o = updt_i.price[L2_LOG_MEM_SIZE:1];

            arr_d[1] = updt_i;
            out_size_all_d = out_size_all_q - updt_i.shares;
            out_size_in_range_d = out_size_in_range_q - updt_i.shares;
            updt_ing_d = '0;
        end

        if (half_dec_book_i.valid) begin
            error_state = updt_ing_q;
            error_init = !initialized_q;
            // assert #0 (!updt_ing_q) else $error("unexpected order input while waiting for updt");

            for (int i = 0; i < 2; i++) begin
                arr_mod[i] = is_add ?
                    arr_q[i].shares + {32'b0, half_dec_book_i.shares} :
                    arr_q[i].shares - {32'b0, half_dec_book_i.shares};
            end

            if (!arr_q[0].valid ||
                        (IS_BUY && arr_q[0].price < half_dec_book_i.price) ||
                        (!IS_BUY && arr_q[0].price > half_dec_book_i.price)) begin
                arr_chng[0] = INSERT;
                out_flag = '0;
                ins_flag = 1'b1;
            end else if (arr_q[0].price == half_dec_book_i.price) begin
                unique if (arr_mod[0] == '0) begin
                    // price level depletion
                    arr_chng[0] = BOTTOM;
                    del_flag = 1'b1;
                end else if (arr_mod[0] > '0) begin
                    arr_chng[0] = MODIFY;
                    mod_flag = 1'b1;
                end
                out_flag = '0;
            end else begin
                arr_chng[0] = HOLD;
            end

            if (ins_flag) begin
                arr_chng[1] = TOP;
            end else if (del_flag) begin
                arr_chng[1] = BOTTOM;
            end else if (mod_flag) begin
                arr_chng[1] = HOLD;
            end else if (!arr_q[1].valid ||
                        (IS_BUY && arr_q[1].price < half_dec_book_i.price) ||
                        (!IS_BUY && arr_q[1].price > half_dec_book_i.price)) begin
                arr_chng[1] = INSERT;
                out_flag = '0;
                ins_flag = 1'b1;
            end else if (arr_q[1].price == half_dec_book_i.price) begin
                unique if (arr_mod[1] == '0) begin
                    // price level depletion
                    arr_chng[1] = BOTTOM;
                    del_flag = 1'b1;
                end else if (arr_mod[1] > '0) begin
                    arr_chng[1] = MODIFY;
                    mod_flag = 1'b1;
                end
                out_flag = '0;
            end else begin
                arr_chng[1] = HOLD;
            end

            unique case (arr_chng[0])
                HOLD:    arr_d[0] = arr_q[0];
                MODIFY:  arr_d[0].shares = arr_mod[0];
                BOTTOM:  arr_d[0] = arr_q[1];
                INSERT:  arr_d[0] = word_ins;
                default: error_enum = 1;
            endcase

            unique case (arr_chng[1])
                HOLD:    arr_d[1] = arr_q[1];
                MODIFY:  arr_d[1].shares = arr_mod[1];
                TOP:     arr_d[1] = arr_q[0];
                BOTTOM: begin
                    arr_d[1].valid = '0;
                    arr_d[1].shares = '0;
                end
                INSERT:  arr_d[1] = word_ins;
                default: error_enum = 1;
            endcase

            unique if (ins_flag) begin
                // BBO_DEPTHth top price evicted from BBO
                out_size_all_d = out_size_all_q + arr_q[1].shares;
                in_range = (IS_BUY && arr_q[1].price >= price_bound_q) ||
                   (!IS_BUY && arr_q[1].price <= price_bound_q);
                out_size_in_range_d = in_range ? (out_size_in_range_q + arr_q[1].shares) : out_size_in_range_q;
            end else if (del_flag) begin
                updt_req_d = updt_able_all_q && updt_able_in_range_q;
                updt_ing_d = updt_req_d;
                error_updt = updt_able_all_q && !updt_able_in_range_q;
            end else if (out_flag) begin
                // price past top BBO_DEPTH price levels
                out_size_all_d = is_add ?
                                 (out_size_all_q + {32'b0, half_dec_book_i.shares}) :
                                 (out_size_all_q - {32'b0, half_dec_book_i.shares});

                in_range = (IS_BUY && half_dec_book_i.price >= price_bound_q) ||
                        (!IS_BUY && half_dec_book_i.price <= price_bound_q);

                out_size_in_range_d = in_range ? (is_add ?
                                      (out_size_in_range_q + {32'b0, half_dec_book_i.shares}) :
                                      (out_size_in_range_q - {32'b0, half_dec_book_i.shares})) :
                                      out_size_in_range_q;
            end
        end

        half_res_o = arr_q[0];

        half_error_o = error_state | error_init | error_enum | error_updt;
    end

endmodule
