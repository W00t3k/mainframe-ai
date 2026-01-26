"""Screen display functions"""
from colorama import Fore, Back, Style

def print_trans(history, num, header):
    """Print a transaction"""
    trans = history[num]
    if header:
        print("\n", Fore.BLUE, "View Transaction", Fore.RESET)
        print(Fore.BLUE, "================", Fore.RESET)
    print("\n", Fore.YELLOW, num, Fore.BLUE, trans.timestamp, Fore.CYAN, trans.key,
          "\t", Fore.BLUE, trans.host, trans.comment, Fore.RESET)
    print("  Req : ", trans.request.stringbuffer[0])
    for field in trans.data:
        print("  Data: row:", field.row, "col:", field.col, "str:", Fore.RED, field.contents, Fore.RESET)
    print("  Resp: ", trans.response.stringbuffer[0], '\n')

def print_history(history):
    """Print transaction history"""
    print("\n", Fore.BLUE, "Transaction List", Fore.RESET)
    print(Fore.BLUE, "================", Fore.RESET, "\n")
    for count, trans in enumerate(history):
        print(Fore.YELLOW, count, Fore.BLUE, trans.timestamp, Fore.CYAN, trans.key,
              "\t", Fore.BLUE, trans.host, trans.comment, Fore.RESET)
        print("  Req : ", trans.request.stringbuffer[0])
        for field in trans.data:
            fieldtxt = field.contents.strip()
            if len(fieldtxt) > 0:
                print("  Data: row:", field.row, "col:", field.col, "str:", Fore.RED, fieldtxt, Fore.RESET)
        print("  Resp: ", trans.response.stringbuffer[0], "\n")
