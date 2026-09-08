module moldudp64_parser_interface (
    input  logic        clk_i,
    input  logic        rst_ni,

    input  logic        axis_tvalid_i,
    input  logic        axis_tlast_i,
    input  logic [31:0] axis_tdata_i,
    input  logic  [3:0] axis_tkeep_i,
    output logic        axis_tready_o,

    output logic        ip_data_v_o,
    output logic [31:0] ip_data_o,
    output logic        ip_data_tlast_o,

    output logic        error_o
);

    moldudp64_parser moldudp64_parser (
        .clk_i,
        .rst_ni,
        .axis_tvalid_i,
        .axis_tlast_i,
        .axis_tdata_i,
        .axis_tkeep_i,
        .axis_tready_o,
        .ip_data_v_o,
        .ip_data_o,
        .ip_data_tlast_o,
        .np_error_o(error_o)
    );
endmodule

module moldudp64_parser (
    input  logic        clk_i,
    input  logic        rst_ni,

    input  logic        axis_tvalid_i,
    input  logic        axis_tlast_i,
    input  logic [31:0] axis_tdata_i,
    input  logic  [3:0] axis_tkeep_i,
    output logic        axis_tready_o,

    output logic        ip_data_v_o,
    output logic [31:0] ip_data_o,
    output logic        ip_data_tlast_o,

    output logic        np_error_o
);

    typedef enum logic[2:0] {IDLE, SESSION_1, SESSION_2, SEQ_NUM_1, SEQ_NUM_2, MSG} np_state_e;

    // moldudp64 header
    logic [79:0] session_id_q, session_id_d;
    logic [31:0] compare_q, compare_d;
    logic [63:0] seq_expect_q, seq_expect_d;

    // message byte counting
    // Assume all messages < 255 bytes long, ignore first byte of length field
    logic [15:0] msg_left_q, msg_left_d;
    logic  [7:0] bytes_left_q, bytes_left_d; // # of bytes left in curr msg + 1, including in incoming word.
    logic        first_pkt_flag_q, first_pkt_flag_d;

    logic        ip_data_v_d;
    logic [31:0] ip_data_d;
    logic        ip_data_tlast_d;

    np_state_e   state_q, state_d; // naming of states denotes what information has been received already

    always_ff @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            seq_expect_q        <= 64'b1;

            msg_left_q          <= '0;
            bytes_left_q        <= '0;
            first_pkt_flag_q    <= 1'b1;

            ip_data_v_o         <= '0;

            state_q             <= IDLE;
        end else begin
            seq_expect_q        <= seq_expect_d;

            msg_left_q          <= msg_left_d;
            bytes_left_q        <= bytes_left_d;
            first_pkt_flag_q    <= first_pkt_flag_d;

            ip_data_v_o         <= ip_data_v_d;

            state_q             <= state_d;
        end
    end

    always_ff @(posedge clk_i) begin
        session_id_q        <= session_id_d;
        compare_q           <= compare_d;

        ip_data_o           <= ip_data_d;
        ip_data_tlast_o     <= ip_data_tlast_d;
    end

    logic tlast_expected;
    logic [3:0] tkeep_expected;
    logic error_pkt_len, error_session_id, error_seq, error_state;
    always_comb begin
        error_pkt_len       = '0;
        error_session_id    = '0;
        error_seq           = '0;
        error_state         = '0;

        axis_tready_o       = 1'b1; // buffering not supported

        session_id_d        = session_id_q;
        compare_d           = compare_q;

        seq_expect_d        = seq_expect_q;

        msg_left_d          = msg_left_q;
        bytes_left_d        = bytes_left_q;
        first_pkt_flag_d    = first_pkt_flag_q;

        ip_data_v_d         = '0;
        ip_data_d           = axis_tdata_i;
        ip_data_tlast_d     = axis_tlast_i;

        state_d             = state_q;

        tlast_expected      = '0;
        tkeep_expected      = 4'hF;

        if (axis_tvalid_i) begin
            unique case (state_q)
                IDLE: begin
                    if (first_pkt_flag_q) begin
                        session_id_d = {axis_tdata_i, session_id_q[47:0]};
                        state_d = SESSION_1;
                    end else if (compare_q != axis_tdata_i) begin
                        // unexpected session id mismatch
                        state_d = IDLE;
                        error_session_id |= 1'b1;
                    end else begin
                        compare_d = session_id_q[47:16];
                        state_d = SESSION_1;
                    end
                end

                SESSION_1: begin
                    if (first_pkt_flag_q) begin
                        session_id_d = {session_id_q[79:48], axis_tdata_i, session_id_q[15:0]};
                        state_d = SESSION_2;
                    end else if (compare_q != axis_tdata_i) begin
                        // unexpected session id mismatch
                        state_d = IDLE;
                        error_session_id |= 1'b1;
                    end else begin
                        compare_d = {session_id_q[15:0], seq_expect_q[63:48]};
                        state_d = SESSION_2;
                    end
                end

                SESSION_2: begin
                    if (first_pkt_flag_q) begin
                        session_id_d = {session_id_q[79:16], axis_tdata_i[31:16]};
                        compare_d = seq_expect_q[47:16];
                        state_d = SEQ_NUM_1;
                    end else if (compare_q[31:16] != axis_tdata_i[31:16]) begin
                        // unexpected session id mismatch
                        state_d = IDLE;
                        error_session_id |= 1'b1;
                    end else if (compare_q[15:0] != axis_tdata_i[15:0]) begin
                        // unexpected seq num mismatch
                        state_d = IDLE;
                        error_seq |= 1'b1;
                    end else begin
                        compare_d = seq_expect_q[47:16];
                        state_d = SEQ_NUM_1;
                    end
                end

                SEQ_NUM_1: begin
                    first_pkt_flag_d = '0;
                    if (compare_q != axis_tdata_i) begin
                        // unexpected seq num mismatch
                        state_d = IDLE;
                        error_seq |= 1'b1;
                    end
                    compare_d = {seq_expect_q[15:0], 16'b0};
                    state_d = SEQ_NUM_2;
                end

                SEQ_NUM_2: begin
                    if (compare_q[31:16] != axis_tdata_i[31:16]) begin
                        state_d = IDLE;
                        error_seq |= 1'b1;
                    end

                    compare_d = session_id_q[79:48];
                    msg_left_d = axis_tdata_i[15:0];

                    seq_expect_d = seq_expect_q + {48'b0, msg_left_d};

                    if (msg_left_d == 0) begin
                        // heartbeat packet, tlast expected
                        state_d = IDLE;
                        tlast_expected |= 1'b1;
                    end else begin
                        bytes_left_d = 8'b1;
                        state_d = MSG;
                    end
                end

                MSG: begin
                    ip_data_v_d = 1'b1;
                    if (bytes_left_q < 8'h6 && msg_left_q == '0) begin
                        // last word of packet incoming, tlast expected
                        // note that bytes_left is +1 from first byte of theoretical next msg_len field
                        bytes_left_d = 8'b1;

                        state_d = IDLE;
                        tlast_expected |= 1'b1;
                        tkeep_expected = {bytes_left_q > 8'h1, bytes_left_q > 8'h2, bytes_left_q > 8'h3, bytes_left_q > 8'h4};
                    end else if (bytes_left_q < 8'h4 && msg_left_q > '0) begin
                        // next message
                        // note: only second byte of 2-byte message length field is read
                        // assume message length < 255 (true for ITCH messages)
                        // any errors effectively caught by "unexpected" tvalid
                        // catch length field errors in ITCH parser
                        msg_left_d = msg_left_q - 16'b1;
                        unique case (bytes_left_q[1:0])
                            2'b00: begin
                                bytes_left_d = axis_tdata_i[31:24] - 8'h2;
                            end
                            2'b01: begin
                                bytes_left_d = axis_tdata_i[23:16] - 8'h1;
                            end
                            2'b10: begin
                                bytes_left_d = axis_tdata_i[15: 8];
                            end
                            2'b11: begin
                                bytes_left_d = axis_tdata_i[ 7: 0] + 8'h1;
                            end
                            default: error_state |= 1'b1;
                        endcase

                        state_d = MSG;
                    end else begin
                        bytes_left_d = bytes_left_q - 8'h4;
                        state_d = MSG;
                    end
                end
                default: begin
                    // unexpected state
                    error_state |= 1'b1;
                    state_d = IDLE;
                end
            endcase

            error_pkt_len |= axis_tkeep_i != tkeep_expected;
            error_pkt_len |= tlast_expected != axis_tlast_i;
        end

        np_error_o = error_pkt_len | error_session_id | error_seq | error_state;
    end
endmodule
