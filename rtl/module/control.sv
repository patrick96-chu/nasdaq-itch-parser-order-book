`include "../include/definitions.sv"

module control_interface
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

    // for purposes of tb, pulse output_v_o on received dec struct.
    output logic        output_v_o,
    output logic        stock_active_o,

    output logic        stock_locate_v_o,
    output logic [15:0] stock_locate_o,

    output logic        book_ready_o,

    output logic        error_o
);

    logic        ip_data_v;
    logic [31:0] ip_data;
    logic        ip_data_tlast;
    logic        np_error;
    moldudp64_parser moldudp64_parser (
        .clk_i,
        .rst_ni,
        .axis_tvalid_i  (axis_tvalid_i),
        .axis_tlast_i   (axis_tlast_i),
        .axis_tdata_i   (axis_tdata_i),
        .axis_tkeep_i   (axis_tkeep_i),
        .axis_tready_o  (axis_tready_o),
        .ip_data_v_o    (ip_data_v),
        .ip_data_o      (ip_data),
        .ip_data_tlast_o(ip_data_tlast),
        .np_error_o     (np_error)
    );

    logic        ip_error;
    logic        stock_locate_v;
    logic [15:0] stock_locate;
    dec_ctrl_s   dec_ctrl;
    dec_book_s   dec_book;
    itch_parser itch_parser (
        .clk_i,
        .rst_ni,
        .ip_data_v_i     (ip_data_v),
        .ip_data_i       (ip_data),
        .ip_data_tlast_i (ip_data_tlast),
        .stock_locate_v_i(stock_locate_v),
        .stock_locate_i  (stock_locate),
        .dec_ctrl_o      (dec_ctrl),
        .oid_hash_o      (),
        .dec_book_o      (dec_book),
        .ip_error_o      (ip_error)
    );

    logic        ctrl_error;
    control control (
        .clk_i,
        .rst_ni,
        .dec_ctrl_i         (dec_ctrl),
        .dec_book_v_i       (dec_book.valid),
        .init_v_i           (init_v_i),
        .init_market_i      (init_market_i),
        .init_stock_symbol_i(init_stock_symbol_i),
        .stock_active_o     (stock_active_o),
        .stock_locate_v_o   (stock_locate_v_o),
        .stock_locate_o     (stock_locate_o),
        .ctrl_error_o       (ctrl_error)
    );

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            output_v_o <= '0;
        end else begin
            output_v_o <= dec_ctrl.valid || dec_book.valid;
        end
    end

    always_comb begin
        book_ready_o = 1'b1;
        error_o = np_error | ip_error | ctrl_error;
    end
endmodule

module control
    import definitions::*;
(
    input  logic        clk_i,
    input  logic        rst_ni,

    input  dec_ctrl_s   dec_ctrl_i,
    input  logic        dec_book_v_i,

    input  logic        init_v_i,
    input  market_e     init_market_i,
    input  logic [63:0] init_stock_symbol_i,

    output logic        stock_active_o, // continuous assertion
    output logic        stock_locate_v_o, // continuous assertion
    output logic [15:0] stock_locate_o,

    output logic        ctrl_error_o
);

    logic        initialized_q;
    market_e     init_market_q;
    logic [63:0] init_stock_symbol_q;

    logic        msg_hours_q, system_hours_q, market_hours_q, msg_hours_d, system_hours_d, market_hours_d;

    logic [15:0] stock_locate_q, stock_locate_d;
    logic        stock_locate_v_q, stock_locate_v_d;

    logic        stock_halt_q, market_halt_q, stock_halt_d, market_halt_d;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            initialized_q       <= '0;

            msg_hours_q         <= '0;
            system_hours_q      <= '0;
            market_hours_q      <= '0;

            stock_locate_v_q    <= '0;

            stock_halt_q        <= '1;
            market_halt_q       <= '0;
        end else begin
            initialized_q       <= init_v_i ? 1'b1 : initialized_q;

            msg_hours_q         <= msg_hours_d;
            system_hours_q      <= system_hours_d;
            market_hours_q      <= market_hours_d;

            stock_locate_v_q    <= stock_locate_v_d;

            stock_halt_q        <= stock_halt_d;
            market_halt_q       <= market_halt_d;
        end
    end

    always_ff @(posedge clk_i) begin
        init_market_q       <= init_v_i ? init_market_i : init_market_q;
        init_stock_symbol_q <= init_v_i ? init_stock_symbol_i : init_stock_symbol_q;
        stock_locate_q      <= stock_locate_d;
    end

    logic msg_expected;
    logic error_init, error_enum;
    logic error_stock_locate, error_msg_hours;
    always_comb begin
        error_init          = '0;
        error_enum          = '0;
        error_stock_locate  = '0;
        error_msg_hours     = '0;

        msg_expected        = msg_hours_q;

        msg_hours_d         = msg_hours_q;
        system_hours_d      = system_hours_q;
        market_hours_d      = market_hours_q;

        stock_locate_d      = stock_locate_q;
        stock_locate_v_d    = stock_locate_v_q;

        stock_halt_d        = stock_halt_q;
        market_halt_d       = market_halt_q;

        stock_active_o      = initialized_q && msg_hours_q && system_hours_q && !stock_halt_q && !market_halt_q;
        stock_locate_v_o    = stock_locate_v_q;
        stock_locate_o      = stock_locate_q;

        if (dec_ctrl_i.valid) begin
            error_init = !initialized_q;

            unique case (dec_ctrl_i.msg_type)
                MSG_EVENT: begin
                    unique case (dec_ctrl_i.event_code)
                        EVENT_O: begin
                            msg_hours_d = 1'b1;
                            msg_expected = 1'b1;
                        end
                        EVENT_S: system_hours_d = 1'b1;
                        EVENT_Q: market_hours_d = 1'b1;
                        EVENT_M: market_hours_d = '0;
                        EVENT_E: system_hours_d = '0;
                        EVENT_C: msg_hours_d = '0;
                        default: error_enum = 1'b1;
                    endcase
                end

                MSG_DIRECTORY: begin
                    if (dec_ctrl_i.stock_symbol == init_stock_symbol_q) begin
                        stock_locate_v_d  = 1'b1;
                        stock_locate_d    = dec_ctrl_i.stock_locate;

                        error_stock_locate = stock_locate_v_q && (stock_locate_q != dec_ctrl_i.stock_locate);
                    end
                end

                MSG_ACTION: begin
                    if (dec_ctrl_i.stock_symbol == init_stock_symbol_q) begin
                        unique case (dec_ctrl_i.trade_action)
                            ACTION_H, ACTION_P: stock_halt_d = 1'b1;
                            ACTION_Q, ACTION_T: stock_halt_d = '0;
                            default: error_enum = 1'b1;
                        endcase
                    end
                end

                MSG_HALT: begin
                    if (dec_ctrl_i.stock_symbol == init_stock_symbol_q) begin
                        if (dec_ctrl_i.market == init_market_q) begin
                            market_halt_d = dec_ctrl_i.is_halt;
                        end
                    end
                end
            endcase

            // assert msg hours true
            error_msg_hours = !msg_expected;
        end else if (dec_book_v_i) begin
            error_init = !initialized_q;
            error_msg_hours = !msg_expected;
        end
        ctrl_error_o = error_init | error_init | error_msg_hours | error_stock_locate;
    end

endmodule
