""" Quickstart script for InstaPy usage """

# imports
from srt_reservation.main import SRT
from srt_reservation.util import parse_cli_args
import telegram
import asyncio

async def main(token ,chat_id, txt): #실행시킬 함수명 임의지정

    bot = telegram.Bot(token = token)
    await bot.send_message(chat_id,text=txt)

if __name__ == "__main__":
    cli_args = parse_cli_args()

    login_id = cli_args.user
    login_psw = cli_args.psw
    dpt_stn = cli_args.dpt
    arr_stn = cli_args.arr
    dpt_dt = cli_args.dt
    dpt_tm = cli_args.tm

    token = cli_args.token
    chat_id = cli_args.chat_id

    num_trains_to_check = cli_args.num

    want_reserve = cli_args.reserve
    want_special = cli_args.special
    want_any = cli_args.any

    quantity = cli_args.quantity

    # srt = SRT(dpt_stn, arr_stn, dpt_dt, dpt_tm, psg_adult, psg_child, num_trains_to_check, want_reserve)
    
    srt = SRT(token, chat_id, dpt_stn, arr_stn, dpt_dt, dpt_tm, num_trains_to_check, want_reserve, want_special, want_any, quantity)
    srt.run(login_id, login_psw)

    print("프로그램 종료!")
    asyncio.run(token, chat_id, main("프로그램 종료!")) #봇 실행하는 코드