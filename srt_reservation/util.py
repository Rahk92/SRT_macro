import argparse

def parse_cli_args():

    parser = argparse.ArgumentParser(description='')

    parser.add_argument("--user", help="Username", type=str, metavar="1234567890")
    parser.add_argument("--psw", help="Password", type=str, metavar="abc1234")
    parser.add_argument("--dpt", help="Departure Station", type=str, metavar="동탄")
    parser.add_argument("--arr", help="Arrival Station", type=str, metavar="동대구")
    parser.add_argument("--dt", help="Departure Date", type=str, metavar="20220118")
    parser.add_argument("--tm", help="Departure Time", type=str, metavar="08, 10, 12, ...")

    parser.add_argument("--notify", help="Telegram Notification", action=argparse.BooleanOptionalAction)
    parser.add_argument("--token", help="Telegram Token", type=str)
    parser.add_argument("--chat_id", help="Telegram Chat ID", type=int)

    parser.add_argument("--num", help="no of trains to check", type=int, metavar="2", default=2)
    parser.add_argument("--reserve", help="Reserve or not", action=argparse.BooleanOptionalAction)
    parser.add_argument("--special", help="Special seat or not", action=argparse.BooleanOptionalAction)
    parser.add_argument("--any", help="Reserve any tickets available", action=argparse.BooleanOptionalAction)
    parser.add_argument("--quantity", help="Quantity of tickets", type=int, metavar="1", default=1)

    args = parser.parse_args()

    return args
