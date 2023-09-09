""" Quickstart script for InstaPy usage """

# imports
from srt_reservation.main import SRT
from srt_reservation.util import parse_cli_args
import telegram


if __name__ == "__main__":
    cli_args = parse_cli_args()

    login_id = cli_args.user
    login_psw = cli_args.psw
    dpt_stn = cli_args.dpt
    arr_stn = cli_args.arr
    dpt_dt = cli_args.dt
    dpt_tm = cli_args.tm
    # psg_adult = cli_args.ad
    # psg_child = cli_args.ch

    num_trains_to_check = cli_args.num
    want_reserve = cli_args.reserve
    want_special = cli_args.special
    quantity = cli_args.quantity
    bot = telegram.Bot(token='5145659919:AAE1g-VNdAFcDYrHS1gBz8xcNZaYKH8nE2k')
    chat_id = 5251774509

    # srt = SRT(dpt_stn, arr_stn, dpt_dt, dpt_tm, psg_adult, psg_child, num_trains_to_check, want_reserve)
    
    srt = SRT(bot, chat_id, dpt_stn, arr_stn, dpt_dt, dpt_tm, num_trains_to_check, want_reserve, want_special, quantity)
    srt.run(login_id, login_psw)
    
    bot.sendMessage(chat_id=chat_id, text="프로그램 종료!")