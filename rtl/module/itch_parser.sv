`include "../include/definitions.sv"

module itch_parser_interface
    import definitions::*;
(
    input  logic        clk_i,
    input  logic        rst_ni,

    input  logic        axis_tvalid_i,
    input  logic        axis_tlast_i,
    input  logic [31:0] axis_tdata_i,
    input  logic  [3:0] axis_tkeep_i,
    output logic        axis_tready_o,

    input  logic        stock_locate_v_i,
    input  logic [15:0] stock_locate_i,

    output dec_ctrl_s   dec_ctrl_o,

    output l3_addr_t    oid_hash_o,
    output dec_book_s   dec_book_o,

    output logic        error_o
);

    logic ip_data_v;
    logic [31:0] ip_data;
    logic ip_data_tlast;
    logic np_error;
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

    logic ip_error;
    itch_parser itch_parser (
        .clk_i,
        .rst_ni,
        .ip_data_v_i     (ip_data_v),
        .ip_data_i       (ip_data),
        .ip_data_tlast_i (ip_data_tlast),
        .stock_locate_v_i(stock_locate_v_i),
        .stock_locate_i  (stock_locate_i),
        .dec_ctrl_o      (dec_ctrl_o),
        .oid_hash_o      (oid_hash_o),
        .dec_book_o      (dec_book_o),
        .ip_error_o      (ip_error)
    );

    always_comb begin
        error_o = np_error | ip_error;
    end
endmodule

module itch_parser
    import definitions::*;
(
    input  logic        clk_i,
    input  logic        rst_ni,

    input  logic        ip_data_v_i,
    input  logic [31:0] ip_data_i,
    input  logic        ip_data_tlast_i,

    input  logic        stock_locate_v_i,
    input  logic [15:0] stock_locate_i,

    output dec_ctrl_s   dec_ctrl_o,

    output l3_addr_t    oid_hash_o, // combinational output
    output dec_book_s   dec_book_o, // registered output, 2 clock edges after oid_hash_o

    output logic        ip_error_o
);

    typedef enum logic [3:0] {
        IDLE, SYS_EVENT, DIRECTORY, TRADING_ACTION, OP_HALT, ADD, EXECUTE, EXECUTE_P, DELETE, REPLACE, IGNORE
    } ip_state_e;

    logic [351:0]   ip_line_q, ip_line_d, line_shifted;
    logic [7:0]     bytes_left_q, bytes_left_d;
    logic           msg_alt_q, msg_alt_d; // add with MPID or cancel

    dec_ctrl_s      dec_ctrl_d;

    logic           match_locate_d, match_locate_q;
    dec_book_s      dec_book_del_d, dec_book_del_q, dec_book_d, dec_book_q;

    ip_state_e      state_q, state_d;

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            bytes_left_q            <= '0;
            msg_alt_q               <= '0;

            dec_ctrl_o.valid        <= '0;

            dec_book_q.valid        <= '0;
            dec_book_del_q.valid    <= '0;

            state_q                 <= IDLE;
        end else begin
            bytes_left_q            <= bytes_left_d;
            msg_alt_q               <= msg_alt_d;

            dec_ctrl_o              <= dec_ctrl_d;

            dec_book_q              <= dec_book_del_q.valid ? dec_book_del_q : dec_book_d;
            dec_book_del_q          <= dec_book_del_d;

            state_q                 <= state_d;
        end
    end

    always_ff @(posedge clk_i) begin
        ip_line_q               <= ip_line_d;

        match_locate_q          <= match_locate_d;
    end

    logic [15:0] msg_len;

    logic error_state, error_msg_len, error_msg_type, error_stock_locate;
    logic error_event_code, error_trade_action, error_market_code, error_halt_code, error_buy_sell;
    always_comb begin
        error_state         = '0;
        error_msg_len       = '0;
        error_msg_type      = '0;
        error_stock_locate  = '0;
        error_event_code    = '0;
        error_trade_action  = '0;
        error_market_code   = '0;
        error_halt_code     = '0;
        error_buy_sell      = '0;

        dec_book_o          = dec_book_q;

        ip_line_d           = ip_data_v_i ? {ip_line_q[319:0], ip_data_i} : ip_line_q;
        bytes_left_d        = bytes_left_q;
        msg_alt_d           = msg_alt_q;

        dec_ctrl_d          = dec_ctrl_o;
        dec_ctrl_d.valid    = '0;

        match_locate_d      = match_locate_q;
        dec_book_del_d      = '0;
        dec_book_d          = dec_book_q;
        dec_book_d.valid    = '0;

        state_d             = state_q;

        unique case (bytes_left_q[1:0])
            2'h0: line_shifted = ip_line_d << 32;
            2'h1: line_shifted = ip_line_d << 8;
            2'h2: line_shifted = ip_line_d << 16;
            2'h3: line_shifted = ip_line_d << 24;
            default: line_shifted = ip_line_d << 32;
        endcase

        if (ip_data_v_i) begin
            if (state_q != IDLE && bytes_left_q < 8'h5) begin
                // message completed; note unexpected tlast already handled in network parser
                state_d = IDLE;
            end

            if (state_q != IDLE) begin
                bytes_left_d = ip_data_tlast_i ? '0 : bytes_left_q - 8'h4;
            end

            unique case (state_q)
                IDLE: begin
                    msg_len = line_shifted[63:48];
                    unique case (bytes_left_q[1:0])
                        2'h0: bytes_left_d = msg_len[7:0] - 8'h2;
                        2'h1: bytes_left_d = msg_len[7:0] - 8'h5;
                        2'h2: bytes_left_d = msg_len[7:0] - 8'h4;
                        2'h3: bytes_left_d = msg_len[7:0] - 8'h3;
                        default: bytes_left_d = msg_len[7:0] - 8'h2;
                    endcase
                    msg_alt_d = 1'b0;

                    // Message Type
                    unique case (line_shifted[47:40])
                        "S": begin
                            // Unexpected msg length
                            error_msg_len = (msg_len != 16'hC);
                            state_d = SYS_EVENT;
                        end
                        "R": begin
                            error_msg_len = (msg_len != 16'h27);
                            state_d = DIRECTORY;
                        end
                        "H": begin
                            error_msg_len = (msg_len != 16'h19);
                            state_d = TRADING_ACTION;
                        end
                        "Y": begin
                            error_msg_len = (msg_len != 16'h14);
                            state_d = IGNORE;
                        end
                        "L": begin
                            error_msg_len = (msg_len != 16'h1A);
                            state_d = IGNORE;
                        end
                        "V": begin
                            error_msg_len = (msg_len != 16'h23);
                            state_d = IGNORE;
                        end
                        "W": begin
                            error_msg_len = (msg_len != 16'hC);
                            state_d = IGNORE;
                        end
                        "K": begin
                            error_msg_len = (msg_len != 16'h1C);
                            state_d = IGNORE;
                        end
                        "J": begin
                            error_msg_len = (msg_len != 16'h23);
                            state_d = IGNORE;
                        end
                        "h": begin
                            error_msg_len = (msg_len != 16'h15);
                            state_d = OP_HALT;
                        end
                        "A": begin
                            error_msg_len = (msg_len != 16'h24);
                            state_d = ADD;
                        end
                        "F": begin
                            error_msg_len = (msg_len != 16'h28);
                            msg_alt_d = 1'b1;
                            state_d = ADD;
                        end
                        "E": begin
                            error_msg_len = (msg_len != 16'h1F);
                            state_d = EXECUTE;
                        end
                        "C": begin
                            error_msg_len = (msg_len != 16'h24);
                            state_d = EXECUTE_P;
                        end
                        "X": begin
                            error_msg_len = (msg_len != 16'h17);
                            msg_alt_d = 1'b1;
                            state_d = EXECUTE;
                        end
                        "D": begin
                            error_msg_len = (msg_len != 16'h13);
                            state_d = DELETE;
                        end
                        "U": begin
                            error_msg_len = (msg_len != 16'h23);
                            state_d = REPLACE;
                        end
                        "P": begin
                            error_msg_len = (msg_len != 16'h2C);
                            state_d = IGNORE;
                        end
                        "Q": begin
                            error_msg_len = (msg_len != 16'h28);
                            state_d = IGNORE;
                        end
                        "B": begin
                            error_msg_len = (msg_len != 16'h13);
                            state_d = IGNORE;
                        end
                        "I": begin
                            error_msg_len = (msg_len != 16'h32);
                            state_d = IGNORE;
                        end
                        "N": begin
                            error_msg_len = (msg_len != 16'h14);
                            state_d = IGNORE;
                        end
                        "O": begin
                            error_msg_len = (msg_len != 16'h30);
                            state_d = IGNORE;
                        end
                        default: begin
                            // not expected message
                            error_msg_type = 1'b1;
                        end
                    endcase
                end

                SYS_EVENT: begin
                    if (bytes_left_q < 8'h5 && bytes_left_q > 8'h0) begin
                        dec_ctrl_d.valid = 1'b1;
                        dec_ctrl_d.msg_type = MSG_EVENT;
                        unique case (line_shifted[39:32])
                            "O": dec_ctrl_d.event_code = EVENT_O;
                            "S": dec_ctrl_d.event_code = EVENT_S;
                            "Q": dec_ctrl_d.event_code = EVENT_Q;
                            "M": dec_ctrl_d.event_code = EVENT_M;
                            "E": dec_ctrl_d.event_code = EVENT_E;
                            "C": dec_ctrl_d.event_code = EVENT_C;
                            default: error_event_code = 1'b1;
                        endcase
                    end
                end

                DIRECTORY: begin
                    if (bytes_left_q < 8'h19 && bytes_left_q > 8'h14) begin
                        dec_ctrl_d.valid = 1'b1;
                        dec_ctrl_d.msg_type = MSG_DIRECTORY;
                        dec_ctrl_d.stock_locate = line_shifted[175:160];
                        dec_ctrl_d.stock_symbol = line_shifted[95:32];
                    end
                end

                TRADING_ACTION: begin
                    if (bytes_left_q < 8'h9 && bytes_left_q > 8'h4) begin
                        dec_ctrl_d.valid = 1'b1;
                        dec_ctrl_d.msg_type = MSG_ACTION;
                        dec_ctrl_d.stock_locate = line_shifted[191:176];
                        dec_ctrl_d.stock_symbol = line_shifted[111:48];
                        unique case (line_shifted[47:40])
                            "H": dec_ctrl_d.trade_action = ACTION_H;
                            "P": dec_ctrl_d.trade_action = ACTION_P;
                            "Q": dec_ctrl_d.trade_action = ACTION_Q;
                            "T": dec_ctrl_d.trade_action = ACTION_T;
                            default: error_trade_action = 1'b1;
                        endcase
                    end
                end

                OP_HALT: begin
                    if (bytes_left_q < 8'h5 && bytes_left_q > 8'h0) begin
                        dec_ctrl_d.valid = 1'b1;
                        dec_ctrl_d.msg_type = MSG_HALT;
                        dec_ctrl_d.stock_locate = line_shifted[191:176];
                        dec_ctrl_d.stock_symbol = line_shifted[111:48];
                        unique case (line_shifted[47:40])
                            "Q": dec_ctrl_d.market = Q;
                            "B": dec_ctrl_d.market = B;
                            "X": dec_ctrl_d.market = X;
                            default: error_market_code = 1'b1;
                        endcase
                        unique case (line_shifted[39:32])
                            "H": dec_ctrl_d.is_halt = 1'b1;
                            "T": dec_ctrl_d.is_halt = 1'b0;
                            default: error_halt_code = 1'b1;
                        endcase
                    end
                end

                ADD: begin
                    if ((bytes_left_q < 8'hD && bytes_left_q > 8'h8 && msg_alt_q)
                        || (bytes_left_q < 8'h9 && bytes_left_q > 8'h4 && !msg_alt_q)) begin
                        // send oid hash 2 cycles earlier (non-registered output)
                        dec_book_d.order_id = line_shifted[199:136];

                        // calculate stock_locate match 1 cycle earlier
                        error_stock_locate = !stock_locate_v_i;
                        match_locate_d = line_shifted[279:264] == stock_locate_i;
                    end else if ((bytes_left_q < 8'h9 && bytes_left_q > 8'h4 && msg_alt_q)
                        || (bytes_left_q < 8'h5 && bytes_left_q > 8'h0 && !msg_alt_q)) begin
                        dec_book_d.valid = match_locate_q;
                        dec_book_d.msg_type = MSG_ADD;
                        dec_book_d.has_rep = '0;
                        unique case (line_shifted[167:160])
                            "B": dec_book_d.is_buy = 1'b1;
                            "S": dec_book_d.is_buy = 1'b0;
                            default: error_buy_sell = 1'b1;
                        endcase
                        dec_book_d.shares = line_shifted[159:128];
                        dec_book_d.price = line_shifted[63:32];
                    end
                end

                EXECUTE: begin
                    if ((bytes_left_q < 8'h9 && bytes_left_q > 8'h4 && msg_alt_q)
                        || (bytes_left_q < 8'h11 && bytes_left_q > 8'hC && !msg_alt_q)) begin
                        // send oid hash 2 cycles earlier (non-registered output)
                        dec_book_d.order_id = line_shifted[95:32];

                        // calculate stock_locate match 1 cycle earlier
                        error_stock_locate = !stock_locate_v_i;
                        match_locate_d = line_shifted[175:160] == stock_locate_i;
                    end else if ((bytes_left_q < 8'h5 && bytes_left_q > 8'h0 && msg_alt_q)
                        || (bytes_left_q < 8'hD && bytes_left_q > 8'h8 && !msg_alt_q)) begin
                        dec_book_d.valid = match_locate_q;
                        dec_book_d.msg_type = MSG_REDUCE;
                        dec_book_d.has_rep = '0;
                        dec_book_d.shares = line_shifted[63:32];
                    end
                end

                EXECUTE_P: begin
                    if (bytes_left_q < 8'h15 && bytes_left_q > 8'h10) begin
                        // send oid hash 2 cycles earlier (non-registered output)
                        dec_book_d.order_id = line_shifted[103:40];

                        // calculate stock_locate match 1 cycle earlier
                        error_stock_locate = !stock_locate_v_i;
                        match_locate_d = line_shifted[183:168] == stock_locate_i;
                    end else if (bytes_left_q < 8'h11 && bytes_left_q > 8'hC) begin
                        dec_book_d.valid = match_locate_q;
                        dec_book_d.msg_type = MSG_REDUCE;
                        dec_book_d.has_rep = '0;
                        dec_book_d.shares = line_shifted[71:40];
                    end
                end

                DELETE: begin
                    if (bytes_left_q < 8'h9 && bytes_left_q > 8'h4) begin
                        // calculate stock_locate match 1 cycle earlier
                        error_stock_locate = !stock_locate_v_i;
                        match_locate_d = line_shifted[143:128] == stock_locate_i;
                    end else if (bytes_left_q < 8'h5 && bytes_left_q > 8'h0) begin
                        // oid not available until last cycle.
                        // combinationally output oid hash, but dec_book_d not valid until next cycle.
                        dec_book_d.order_id = line_shifted[95:32];

                        dec_book_del_d.valid = match_locate_q;
                        dec_book_del_d.msg_type = MSG_DELETE;
                        dec_book_d.has_rep = '0;
                        dec_book_del_d.order_id = dec_book_d.order_id;
                    end
                end

                REPLACE: begin
                    // replace treated as delete order followed by add order
                    if (bytes_left_q < 8'h19 && bytes_left_q > 8'h14) begin
                        // calculate stock_locate match 1 cycle earlier
                        error_stock_locate = !stock_locate_v_i;
                        match_locate_d = line_shifted[143:128] == stock_locate_i;
                    end else if (bytes_left_q < 8'h15 && bytes_left_q > 8'h10) begin
                        // oid not available until last cycle (of delete-relevant bytes).
                        // combinationally output oid hash, but dec_book_d not valid until next cycle.
                        dec_book_d.order_id = line_shifted[95:32];

                        dec_book_del_d.valid = match_locate_q;
                        dec_book_del_d.msg_type = MSG_DELETE;
                        dec_book_del_d.has_rep = 1'b1;
                        dec_book_del_d.order_id = dec_book_d.order_id;
                    end else if (bytes_left_q < 8'h9 && bytes_left_q > 8'h4) begin
                        // send oid hash 2 cycles earlier (non-registered output)
                        dec_book_d.order_id = line_shifted[127:64];
                    end else if (bytes_left_q < 8'h5 && bytes_left_q > 8'h0) begin
                        dec_book_d.valid = match_locate_q; // previously calculated during delete bytes
                        dec_book_d.msg_type = MSG_REPLACE;
                        dec_book_d.has_rep = '0;
                        dec_book_d.shares = line_shifted[95:64];
                        dec_book_d.price = line_shifted[63:32];
                    end
                end

                IGNORE: ;// do nothing
                default: begin
                    // unexpected state
                    error_state = 1;
                    state_d = IDLE;
                end
            endcase

        end

        // oid_hash_o = dec_book_d.order_id[2*L3_LOG_ADDR_SIZE - 1:L3_LOG_ADDR_SIZE] ^
        //                 dec_book_d.order_id[L3_LOG_ADDR_SIZE - 1:0];
        oid_hash_o = dec_book_d.order_id[L3_LOG_ADDR_SIZE - 1:0];

        ip_error_o = error_state | error_msg_len | error_msg_type | error_stock_locate |
                     error_event_code | error_trade_action | error_market_code | error_halt_code | error_buy_sell;
    end
endmodule
