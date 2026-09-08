// Auto-generated file. DO NOT EDIT.
`ifndef DEFINITIONS
`define DEFINITIONS
// `define SYNTH

package definitions;
    localparam int L3_LOG_ADDR_SIZE = 11;
    localparam int L3_LOG_LINE_SIZE = 3;
    localparam int L3_LOG_MEM_SIZE  = 14;
    localparam int L3_WORD_SIZE     = 130;
    localparam int L3_LOG_CAM_SIZE  = 3;
    localparam int L3_CAM_SIZE      = 8;
    localparam int L2_LOG_MEM_SIZE  = 11;
    localparam int L2_MEM_SIZE      = 2048;
    localparam int L2_BLOCK_LOG_W   = 5;
    localparam int L2_BLOCK_W       = 32;
    localparam int L2_BLOCK_LOG_CNT = 6;
    localparam int L2_BLOCK_CNT     = 64;
    localparam int BBO_LOG_DEPTH    = 1;
    localparam int BBO_DEPTH        = 2;

    // order book
    typedef struct packed {
        logic        bid_valid;
        logic [31:0] bid_price;
        logic [63:0] bid_shares;
        logic        off_valid;
        logic [31:0] off_price;
        logic [63:0] off_shares;
        logic [31:0] spread;
    } bbo_s;

    // L3 order table
    typedef logic [L3_LOG_ADDR_SIZE-1:0] l3_addr_t;
    typedef logic [L3_LOG_LINE_SIZE-1:0] line_idx_t;

    typedef struct packed {
        logic        valid;
        logic [63:0] order_id;
        logic        is_buy;
        logic [31:0] shares;
        logic [31:0] price;
    } l3_word_s;

    typedef l3_word_s [(1 << L3_LOG_LINE_SIZE) - 1:0] l3_line_t;

    // L2 price ladder
    typedef logic [L2_LOG_MEM_SIZE - 1:0] l2_addr_t;

    typedef struct packed {
        logic [31:0] price;
        logic [63:0] shares;
    } l2_word_s;

    // BBO
    typedef enum logic [2:0] {HOLD, MODIFY, TOP, BOTTOM, INSERT} bbo_arr_chng_e;

    typedef struct packed {
        logic        valid;
        logic [31:0] price;
        logic [63:0] shares;
    } bbo_word_s;

    // Control-side decoded signals
    typedef enum logic [1:0] {MSG_EVENT, MSG_DIRECTORY, MSG_ACTION, MSG_HALT} ctrl_msg_type_e;
    typedef enum logic [2:0] {EVENT_O, EVENT_S, EVENT_Q, EVENT_M, EVENT_E, EVENT_C} event_code_e;
    typedef enum logic [1:0] {ACTION_H, ACTION_P, ACTION_Q, ACTION_T} trade_action_e;
    typedef enum logic [1:0] {Q, B, X} market_e;

    typedef struct packed {
        logic           valid;

        ctrl_msg_type_e msg_type;

        logic [15:0]    stock_locate;

        // S msg type
        event_code_e    event_code;

        // R msg type
        logic [63:0]    stock_symbol;

        // H msg type
        trade_action_e  trade_action;

        // h msg type
        market_e        market;
        logic           is_halt;
    } dec_ctrl_s;

    // order book-side decoded signals

    typedef enum logic [1:0] {MSG_ADD, MSG_REPLACE, MSG_REDUCE, MSG_DELETE} book_msg_type_e;

    typedef struct packed {
        logic           valid;

        book_msg_type_e msg_type;
        logic           has_rep;

        logic [63:0]    order_id;

        logic           is_buy;
        logic [31:0]    shares;
        logic [31:0]    price;
    } dec_book_s;

endpackage

`endif
