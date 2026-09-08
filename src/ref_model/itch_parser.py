from src.ref_model.structs import *

class ITCHParser:
    """
    Parses ITCH messages.
    """

    @staticmethod
    def parse_msg(msg: bytes):
        """
        Parses a single ITCH message as a bytes array.
        First 2 bytes are the message length field from MoldUDP64 protocol.
        """
        msg_byte_len = int.from_bytes(msg[0:2], "big")
        # this should already be caught by mold parser due to unexpected tlast
        # if len(msg) != msg_byte_len + 2:
        #     yield ITCHParserResult.error("Msg length did not match length field.")
        #     return
        assert len(msg) == msg_byte_len + 2, "Msg length did not match length field."

        # common fields
        msg_type = chr(msg[2])
        stock_locate = int.from_bytes(msg[3:5], "big")
        try:
            stock_symbol = msg[13:21].decode()
        except UnicodeDecodeError:
            pass
        order_id = int.from_bytes(msg[13:21], "big")

        match msg_type:
            case 'S':
                if msg_byte_len != 12:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                try:
                    event_code = SystemEventCode(msg[13])
                except ValueError:
                    yield ITCHParserResult.error("Invalid event code.")
                    return

                yield ITCHParserResult(parsed_msg=SystemEventMsg(
                    stock_locate = stock_locate,
                    event_code   = event_code,
                ))

            case 'R':
                if msg_byte_len != 39:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=DirectoryMsg(
                    stock_locate = stock_locate,
                    stock_symbol = stock_symbol,
                ))

            case 'H':
                if msg_byte_len != 25:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                try:
                    trade_action = TradeActionCode(msg[21])
                except ValueError:
                    yield ITCHParserResult.error("Invalid trading action.")
                    return

                yield ITCHParserResult(parsed_msg=TradeActionMsg(
                    stock_locate = stock_locate,
                    stock_symbol = stock_symbol,
                    trade_action = trade_action,
                ))

            case 'Y':
                if msg_byte_len != 20:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=ITCHMsg(
                    msg_type     = ITCHMsgType.IGNORE,
                    stock_locate = stock_locate,
                ))

            case 'L':
                if msg_byte_len != 26:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=ITCHMsg(
                    msg_type     = ITCHMsgType.IGNORE,
                    stock_locate = stock_locate,
                ))

            case 'V':
                if msg_byte_len != 35:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=ITCHMsg(
                    msg_type     = ITCHMsgType.IGNORE,
                    stock_locate = stock_locate,
                ))

            case 'W':
                if msg_byte_len != 12:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=ITCHMsg(
                    msg_type     = ITCHMsgType.IGNORE,
                    stock_locate = stock_locate,
                ))

            case 'K':
                if msg_byte_len != 28:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=ITCHMsg(
                    msg_type     = ITCHMsgType.IGNORE,
                    stock_locate = stock_locate,
                ))

            case 'J':
                if msg_byte_len != 35:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=ITCHMsg(
                    msg_type     = ITCHMsgType.IGNORE,
                    stock_locate = stock_locate,
                ))

            case 'h':
                if msg_byte_len != 21:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                market_code = chr(msg[21])
                if market_code not in "QBX":
                    yield ITCHParserResult.error("Invalid market code.")
                    return

                is_halt = False
                match chr(msg[22]):
                    case 'H':
                        is_halt = True
                    case 'T':
                        is_halt = False
                    case _:
                        yield ITCHParserResult.error("Invalid op halt code.")
                        return

                yield ITCHParserResult(parsed_msg=OpHaltMsg(
                    stock_locate = stock_locate,
                    stock_symbol = stock_symbol,
                    market_code  = market_code,
                    is_halt      = is_halt,
                ))

            case 'A':
                if msg_byte_len != 36:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                is_buy = False
                match chr(msg[21]):
                    case 'B':
                        is_buy = True
                    case 'S':
                        is_buy = False
                    case _:
                        yield ITCHParserResult.error("Invalid buy/sell indicator.")
                        return

                yield ITCHParserResult(parsed_msg=AddOrderMsg(
                    stock_locate = stock_locate,
                    order_id     = order_id,
                    is_buy       = is_buy,
                    shares       = int.from_bytes(msg[22:26], "big"),
                    price        = int.from_bytes(msg[34:38], "big"),
                ))

            case 'F':
                if msg_byte_len != 40:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                is_buy = False
                match chr(msg[21]):
                    case 'B':
                        is_buy = True
                    case 'S':
                        is_buy = False
                    case _:
                        yield ITCHParserResult.error("Invalid buy/sell indicator.")
                        return

                yield ITCHParserResult(parsed_msg=AddOrderMsg(
                    stock_locate = stock_locate,
                    order_id     = order_id,
                    is_buy       = is_buy,
                    shares       = int.from_bytes(msg[22:26], "big"),
                    price        = int.from_bytes(msg[34:38], "big"),
                ))

            case 'E':
                if msg_byte_len != 31:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=ReduceOrderMsg(
                    stock_locate = stock_locate,
                    order_id     = order_id,
                    shares       = int.from_bytes(msg[21:25], "big"),
                ))

            case 'C':
                if msg_byte_len != 36:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=ReduceOrderMsg(
                    stock_locate = stock_locate,
                    order_id     = order_id,
                    shares       = int.from_bytes(msg[21:25], "big"),
                ))

            case 'X':
                if msg_byte_len != 23:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=ReduceOrderMsg(
                    stock_locate = stock_locate,
                    order_id     = order_id,
                    shares       = int.from_bytes(msg[21:25], "big"),
                ))

            case 'D':
                if msg_byte_len != 19:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=DeleteOrderMsg(
                    stock_locate = stock_locate,
                    order_id     = order_id,
                ))

            case 'U':
                if msg_byte_len != 35:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=DeleteOrderMsg(
                    stock_locate = stock_locate,
                    order_id     = order_id,
                ))

                yield ITCHParserResult(parsed_msg=ReplaceOrderMsg(
                    stock_locate = stock_locate,
                    order_id     = int.from_bytes(msg[21:29], "big"),
                    shares       = int.from_bytes(msg[29:33], "big"),
                    price        = int.from_bytes(msg[33:37], "big"),
                ))

            case 'P':
                if msg_byte_len != 44:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=ITCHMsg(
                    msg_type     = ITCHMsgType.IGNORE,
                    stock_locate = stock_locate,
                ))

            case 'Q':
                if msg_byte_len != 40:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=ITCHMsg(
                    msg_type     = ITCHMsgType.IGNORE,
                    stock_locate = stock_locate,
                ))

            case 'B':
                if msg_byte_len != 17:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=ITCHMsg(
                    msg_type     = ITCHMsgType.IGNORE,
                    stock_locate = stock_locate,
                ))

            case 'I':
                if msg_byte_len != 50:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=ITCHMsg(
                    msg_type     = ITCHMsgType.IGNORE,
                    stock_locate = stock_locate,
                ))

            case 'N':
                if msg_byte_len != 20:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=ITCHMsg(
                    msg_type     = ITCHMsgType.IGNORE,
                    stock_locate = stock_locate,
                ))

            case 'O':
                if msg_byte_len != 48:
                    yield ITCHParserResult.error("Unexpected msg byte length.")
                    return

                yield ITCHParserResult(parsed_msg=ITCHMsg(
                    msg_type     = ITCHMsgType.IGNORE,
                    stock_locate = stock_locate,
                ))

            case _:
                yield ITCHParserResult.error("Unexpected msg_type field.")
                return
