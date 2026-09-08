from collections.abc import Iterator, Iterable

from src.ref_model.structs import ModuleResult

def assert_matching_result(result, expect):
    if isinstance(result, Iterable) and isinstance(expect, list):
        for i, res in enumerate(result):
            assert res == expect[i], f"\nExpected: {expect[i]}\nGot result: {res}"
    elif isinstance(result, ModuleResult) and isinstance(expect, ModuleResult):
        assert result == expect, f"\nExpected: {expect}\nGot result: {result}"
    else:
        raise TypeError("result and expect must be of same type.")

def assert_error_msg(result, error_code_base: str):
    if isinstance(result, Iterable):
        for res in result:
            if res.error_flag:
                print("Received error: " + res.error_code)
                assert error_code_base in res.error_code
                return

    elif isinstance(result, ModuleResult):
        if result.error_flag:
            print("Received error: " + result.error_code)
            assert error_code_base in result.error_code
            return

    assert False, "Expected error but received none."

def assert_no_error(result):
    if (isinstance(result, ModuleResult)):
        if result.error_flag:
            print("Received unexpected error: " + result.error_code)
        assert not result.error_flag
        return

    for res in result:
        if res.error_flag:
            print("Received unexpected error: " + res.error_code)
        assert not res.error_flag

def assert_empty_result(result):
    if result is None:
        # correct
        return
    
    for res in result:
        print(res.error_code)
        assert False, "Expected empty result."
