from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class Params:
    # independent parameters
    L3_LOG_ADDR_SIZE: int = 11
    L3_LOG_LINE_SIZE: int = 3
    L3_WORD_SIZE    : int = 130
    L3_LOG_CAM_SIZE : int = 3
    L2_LOG_MEM_SIZE : int = 11
    L2_BLOCK_LOG_W  : int = 5
    BBO_LOG_DEPTH   : int = 1

    # derived parameters
    L3_LOG_MEM_SIZE : int = field(init=False)
    L3_CAM_SIZE     : int = field(init=False)
    L2_MEM_SIZE     : int = field(init=False)
    L2_BLOCK_W      : int = field(init=False)
    L2_BLOCK_LOG_CNT: int = field(init=False)
    L2_BLOCK_CNT    : int = field(init=False)
    BBO_DEPTH       : int = field(init=False)

    def __post_init__(self):
        self.L3_LOG_MEM_SIZE  = self.L3_LOG_ADDR_SIZE + self.L3_LOG_LINE_SIZE
        self.L3_CAM_SIZE      = 1 << self.L3_LOG_CAM_SIZE
        self.L2_MEM_SIZE      = 1 << self.L2_LOG_MEM_SIZE
        self.L2_BLOCK_W       = 1 << self.L2_BLOCK_LOG_W
        self.L2_BLOCK_LOG_CNT = self.L2_LOG_MEM_SIZE - self.L2_BLOCK_LOG_W
        self.L2_BLOCK_CNT     = 1 << self.L2_BLOCK_LOG_CNT
        self.BBO_DEPTH        = 1 << self.BBO_LOG_DEPTH

    def write_sv_package(self):
        content = f"""// Auto-generated file. DO NOT EDIT.
`ifndef DEFINITIONS
`define DEFINITIONS
// `define SYNTH

package definitions;
    localparam int L3_LOG_ADDR_SIZE = {self.L3_LOG_ADDR_SIZE};
    localparam int L3_LOG_LINE_SIZE = {self.L3_LOG_LINE_SIZE};
    localparam int L3_LOG_MEM_SIZE  = {self.L3_LOG_MEM_SIZE };
    localparam int L3_WORD_SIZE     = {self.L3_WORD_SIZE    };
    localparam int L3_LOG_CAM_SIZE  = {self.L3_LOG_CAM_SIZE };
    localparam int L3_CAM_SIZE      = {self.L3_CAM_SIZE     };
    localparam int L2_LOG_MEM_SIZE  = {self.L2_LOG_MEM_SIZE };
    localparam int L2_MEM_SIZE      = {self.L2_MEM_SIZE     };
    localparam int L2_BLOCK_LOG_W   = {self.L2_BLOCK_LOG_W  };
    localparam int L2_BLOCK_W       = {self.L2_BLOCK_W      };
    localparam int L2_BLOCK_LOG_CNT = {self.L2_BLOCK_LOG_CNT};
    localparam int L2_BLOCK_CNT     = {self.L2_BLOCK_CNT    };
    localparam int BBO_LOG_DEPTH    = {self.BBO_LOG_DEPTH   };
    localparam int BBO_DEPTH        = {self.BBO_DEPTH       };
""" + """
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
"""

        curr_file = Path(__file__).resolve()
        dest_file = curr_file.parent.parent.parent / "rtl" / "include" / "definitions.sv"
        dest_file.write_text(content)


config = Params()

if __name__ == "__main__":
    config.write_sv_package()
