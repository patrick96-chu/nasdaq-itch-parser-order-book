`include "../include/definitions.sv"

module book
    import definitions::*;
(
    input  logic        clk_i,
    input  logic        rst_ni,

    input  logic        init_v_i,
    input  logic [31:0] init_price_base_i,

    input  l3_addr_t    oid_hash_i,
    input  dec_book_s   dec_book_i,

    output logic        book_bbo_res_v_o, // 1 tick pulse
    output bbo_s        book_bbo_res_o, // non-reg output (reg in top module)

    output logic        book_ready_o, // hold high

    output logic        book_error_o
);

    dec_book_s dec_book_updt_q, dec_book_updt_d;
    logic      updt_ing_d, updt_ing_q;

    dec_book_s lookup_dec_book;
    logic      l3_ready;
    logic      l3_error;
    l3_order_table l3_order_table (
        .clk_i,
        .rst_ni,
        .oid_hash_i       (oid_hash_i),
        .l3_dec_book_i    (dec_book_i),
        .lookup_dec_book_o(lookup_dec_book),
        .l3_ready_o       (l3_ready),
        .l3_error_o       (l3_error)
    );

    // logic        prefetch_v_q;
    logic        bid_updt_req;
    l2_addr_t    bid_updt_price_addr;
    logic        off_updt_req;
    l2_addr_t    off_updt_price_addr;
    bbo_word_s   bid_updt, off_updt; // cast output to bbo_word_s
    logic        l2_ready;
    logic        l2_error;
    l2_price_table l2_price_table (
        .clk_i,
        .rst_ni,
        .init_v_i             (init_v_i),
        .init_price_base_i    (init_price_base_i),
        .l2_dec_book_i        (lookup_dec_book),
        // .prefetch_v_i         (prefetch_v_q),
        .bid_updt_req_i       (bid_updt_req),
        .bid_updt_price_addr_i(bid_updt_price_addr),
        .off_updt_req_i       (off_updt_req),
        .off_updt_price_addr_i(off_updt_price_addr),
        .bid_updt_o           (bid_updt),
        .off_updt_o           (off_updt),
        .l2_ready_o           (l2_ready),
        .l2_error_o           (l2_error)
    );

    dec_book_s bbo_dec_book;
    logic      bbo_error;
    bbo_s      bbo_res;
    bbo bbo (
        .clk_i,
        .rst_ni,
        .init_v_i             (init_v_i),
        .init_price_base_i    (init_price_base_i),
        .bbo_dec_book_i       (bbo_dec_book),
        .bid_updt_i           (bid_updt),
        .off_updt_i           (off_updt),
        .bbo_res_o            (bbo_res),
        .bid_updt_req_o       (bid_updt_req),
        .bid_updt_price_addr_o(bid_updt_price_addr),
        .off_updt_req_o       (off_updt_req),
        .off_updt_price_addr_o(off_updt_price_addr),
        .bbo_error_o          (bbo_error)
    );

    logic bbo_res_v_last_q;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            dec_book_updt_q.valid   <= '0;

            updt_ing_q              <= '0;
        end else begin
            updt_ing_q              <= updt_ing_d;
            dec_book_updt_q         <= dec_book_updt_d;

            // prefetch_v_q            <= oid_hash_i;

            bbo_res_v_last_q        <= bbo_dec_book.valid && !bbo_dec_book.has_rep;
        end
    end

    logic error_ready;
    logic error_dec_updt;
    always_comb begin
        error_ready     = '0;
        error_dec_updt  = '0;

        book_ready_o = l2_ready && l3_ready;

        updt_ing_d = updt_ing_q;

        // oid_hash, dec_book_i input to l3 handled in module instantiation

        if (dec_book_i.valid) begin
            error_ready = !book_ready_o;
        end

        // lookup_dec_book input to l2 handled in module instantiation

        bbo_dec_book = lookup_dec_book;
        dec_book_updt_d = lookup_dec_book;
        if (updt_ing_q) begin
            bbo_dec_book.valid = '0;
        end else begin
            dec_book_updt_d.valid = '0;
        end

        if (dec_book_updt_q.valid && !updt_ing_q) begin
            error_dec_updt = lookup_dec_book.valid || dec_book_updt_q.msg_type != MSG_REPLACE;
            dec_book_updt_d.valid = '0;
            bbo_dec_book = dec_book_updt_q;
        end

        if (bid_updt_req || off_updt_req) updt_ing_d = 1'b1;
        if (bid_updt.valid || off_updt.valid) updt_ing_d = '0;

        book_bbo_res_v_o = bbo_res_v_last_q;
        book_bbo_res_o = bbo_res;

        book_error_o = l3_error || l2_error || bbo_error ||
                       error_ready ||
                       error_dec_updt;
    end
endmodule
