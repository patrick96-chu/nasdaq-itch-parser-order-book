`include "definitions.sv"

module top_synth
    import definitions::*;
(
    input  logic        clk_i,
    input  logic        rst_ni,

    input  logic        init_v_i,
    input  market_e     init_market_i,
    input  logic [63:0] init_stock_symbol_i,
    input  logic [31:0] init_price_base_i,

    input  logic        axis_tvalid_i,
    input  logic        axis_tlast_i,
    input  logic [31:0] axis_tdata_i,
    input  logic  [3:0] axis_tkeep_i,
    output logic        axis_tready_o,

    output logic        book_ready_o,

    output logic        bbo_res_v_o,
    output logic        bbo_res_xor_o,

    output logic        error_o
);

    bbo_s bbo_res;
    top top (
        .clk_i,
        .rst_ni,
        .init_v_i,
        .init_market_i,
        .init_stock_symbol_i,
        .init_price_base_i,
        .axis_tvalid_i,
        .axis_tlast_i,
        .axis_tdata_i,
        .axis_tkeep_i,
        .axis_tready_o,
        .book_ready_o,
        .bbo_res_v_o,
        .bbo_res_o(bbo_res),
        .error_o
    );

    always_ff @(posedge clk_i) begin
        bbo_res_xor_o <= ^bbo_res;
    end
endmodule

module top
    import definitions::*;
(
    input  logic        clk_i,
    input  logic        rst_ni,

    input  logic        init_v_i,
    input  market_e     init_market_i,
    input  logic [63:0] init_stock_symbol_i,
    input  logic [31:0] init_price_base_i,

    input  logic        axis_tvalid_i,
    input  logic        axis_tlast_i,
    input  logic [31:0] axis_tdata_i,
    input  logic  [3:0] axis_tkeep_i,
    output logic        axis_tready_o,

    output logic        book_ready_o,

    output logic        bbo_res_v_o,
    output bbo_s        bbo_res_o,

    output logic        error_o
);

    logic        ip_data_v;
    logic [31:0] ip_data;
    logic        ip_data_tlast;
    logic        np_error;
    moldudp64_parser moldudp64_parser (
        .clk_i,
        .rst_ni,
        .axis_tvalid_i  (axis_tvalid_i),    // top level input
        .axis_tlast_i   (axis_tlast_i),     // top level input
        .axis_tdata_i   (axis_tdata_i),     // top level input
        .axis_tkeep_i   (axis_tkeep_i),     // top level input
        .axis_tready_o  (axis_tready_o),    // top level input
        .ip_data_v_o    (ip_data_v),        // itch_parser
        .ip_data_o      (ip_data),          // itch_parser
        .ip_data_tlast_o(ip_data_tlast),    // itch_parser
        .np_error_o     (np_error)          // top
    );

    dec_ctrl_s   dec_ctrl;
    logic        stock_locate_v;
    logic [15:0] stock_locate;
    l3_addr_t    oid_hash;
    dec_book_s   dec_book;
    logic        ip_error;
    itch_parser itch_parser (
        .clk_i,
        .rst_ni,
        .ip_data_v_i     (ip_data_v),       // moldudp64_parser
        .ip_data_i       (ip_data),         // moldudp64_parser
        .ip_data_tlast_i (ip_data_tlast),   // moldudp64_parser
        .stock_locate_v_i(stock_locate_v),  // control
        .stock_locate_i  (stock_locate),    // control
        .dec_ctrl_o      (dec_ctrl),        // control
        .oid_hash_o      (oid_hash),        // book
        .dec_book_o      (dec_book),        // book + .valid control
        .ip_error_o      (ip_error)         // top
    );

    logic        stock_active;
    logic        ctrl_error;
    control control (
        .clk_i,
        .rst_ni,
        .dec_ctrl_i         (dec_ctrl),            // itch_parser
        .dec_book_v_i       (dec_book.valid),      // itch_parser
        .init_v_i           (init_v_i),            // top level input
        .init_market_i      (init_market_i),       // top level input
        .init_stock_symbol_i(init_stock_symbol_i), // top level input
        .stock_active_o     (stock_active),        // top
        .stock_locate_v_o   (stock_locate_v),       // book
        .stock_locate_o     (stock_locate),         // book
        .ctrl_error_o       (ctrl_error)           // top
    );

    logic book_bbo_res_v;
    bbo_s book_bbo_res;
    logic book_error;
    book book (
        .clk_i,
        .rst_ni,
        .init_v_i             (init_v_i),               // top level input
        .init_price_base_i    (init_price_base_i),      // top level input
        .oid_hash_i           (oid_hash),               // itch_parser
        .dec_book_i           (dec_book),               // itch_parser
        .book_bbo_res_v_o     (book_bbo_res_v),         // top
        .book_bbo_res_o       (book_bbo_res),           // top
        .book_ready_o         (book_ready_o),           // top level output
        .book_error_o         (book_error)              // top
    );

    bbo_s bbo_res_d;
    logic error_q;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            bbo_res_v_o <= '0;

            error_q <= '0;
        end else begin
            bbo_res_v_o <= book_bbo_res_v;

            error_q <= error_q || np_error || ip_error || ctrl_error || book_error;
        end
    end

    always_ff @(posedge clk_i) begin
        bbo_res_o <= bbo_res_d;
    end

    always_comb begin
        bbo_res_d = book_bbo_res;
        if (!stock_active) begin
            bbo_res_d.bid_valid = '0;
            bbo_res_d.off_valid = '0;
        end

        error_o = np_error || ip_error || ctrl_error || book_error;
    end

endmodule
