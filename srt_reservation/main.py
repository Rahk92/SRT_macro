# -*- coding: utf-8 -*-
import os
import time

from seleniumwire.undetected_chromedriver import ChromeOptions
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TimedOut
from telegram.request import HTTPXRequest
from telegram.ext import ApplicationBuilder
import requests
import asyncio
import json
from random import randint, random
from datetime import datetime
from seleniumwire import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import ElementClickInterceptedException, StaleElementReferenceException, WebDriverException, TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from srt_reservation.exceptions import InvalidStationNameError, InvalidDateError, InvalidDateFormatError, InvalidTimeFormatError
from srt_reservation.validation import station_list

class SRT:
    def __init__(self, args):
    # def __init__(self, notify, token, chat_id, dpt_stn, arr_stn, dpt_dt, dpt_tm, num_trains_to_check=1, want_reserve=False, want_special=False, want_any=False, want_senior=False, want_child=False, quantity=1):
        """
        :param notify: 텔레그램 알림 사용 여부
        :param token: 텔레그램 봇 token
        :param chat_id: 텔레그램 봇 chat_id
        :param dpt_stn: SRT 출발역
        :param arr_stn: SRT 도착역
        :param dpt_dt: 출발 날짜 YYYYMMDD 형태 ex) 20220115
        :param dpt_tm: 출발 시간 hh 형태, 반드시 짝수 ex) 06, 08, 14, ...
        :param num_trains_to_check: 검색 결과 중 예약 가능 여부 확인할 기차의 수 ex) 2일 경우 상위 2개 확인
        :param want_reserve: 예약 대기가 가능할 경우 선택 여부
        :param want_special: 특실 선택 여부
        :param want_any: 특실, 일반실 상관없는 예약 여부
        :param want_senior: 경로 우대 여부
        :param quantity: 총 예매할 기차표 수
        """
        self.login_id = None
        self.login_psw = None

        self.dpt_stn = args.dpt
        self.arr_stn = args.arr
        self.dpt_dt = args.dt
        self.dpt_tm = str(int(args.tm) // 2 * 2).zfill(2)
        self.dpt_tm_offset = 0
        self.real_dpt_tm = args.tm
        
        self.want_senior = args.senior
        self.want_child = args.child

        self.num_trains_to_check = args.num
        self.want_reserve = args.reserve
        self.want_special = args.special
        self.want_any = args.any
        self.driver = None

        self.is_booked = False  # 예약 완료 되었는지 확인용
        self.cnt_refresh = 0  # 새로고침 회수 기록

        self.check_input()
        self.notify = args.notify
        self.token = args.token
        self.chat_id = args.chat_id

        # HTTPXRequest로 타임아웃 설정
        request = HTTPXRequest(
            connect_timeout=10,
            read_timeout=20,
        )
        self.bot = Bot(token=self.token, request=request)
        self.quantity = args.quantity
        self.cnt_quantity = 0

        self.NF_pass_flag = False
        self.key = ""

    async def telegram_send(self, txt):
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=txt)
            print("Telegram 메세지 전송 성공")
        except Exception as e:
            print(f"Telegram 메세지 전송 실패: {e}")

    def check_input(self):
        if self.dpt_stn not in station_list:
            raise InvalidStationNameError(f"출발역 오류. '{self.dpt_stn}' 은/는 목록에 없습니다.")
        if self.arr_stn not in station_list:
            raise InvalidStationNameError(f"도착역 오류. '{self.arr_stn}' 은/는 목록에 없습니다.")
        if not str(self.dpt_dt).isnumeric():
            raise InvalidDateFormatError("날짜는 숫자로만 이루어져야 합니다.")
        try:
            datetime.strptime(str(self.dpt_dt), '%Y%m%d')
        except ValueError:
            raise InvalidDateError("날짜가 잘못 되었습니다. YYYYMMDD 형식으로 입력해주세요.")

    def set_log_info(self, login_id, login_psw):
        self.login_id = login_id
        self.login_psw = login_psw

    def run_driver(self):
        try:
            options = ChromeOptions()
            # options.add_argument('headless')
            options.add_argument("disable-gpu")
            options.add_argument("--no-sandbox")

            options.set_capability(
                "goog:loggingPrefs", {"performance": "ALL", "browser": "ALL"}
            )

            chrome_install = ChromeDriverManager().install()
            folder = os.path.dirname(chrome_install)
            chromedriver_path = os.path.join(folder, "chromedriver.exe")
            service = ChromeService(chromedriver_path)
            # service = ChromeService(executable_path=ChromeDriverManager().install())

            # self.driver = webdriver.Chrome(options=options)
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_window_size(1920, 1080)
            # self.driver.set_window_position(-2560, 0) # dual QHD monitor setting
            self.driver.minimize_window()
            # if self.NF_pass_flag:
            #     self.NF_pass_flag = False
            # self.driver = webdriver.Chrome(executable_path=chromedriver_path)
            # self.driver = webdriver.Chrome(r"F:\Code\Python\srt_reservation-main\chromedriver.exe")
        except Exception as e:
            print(f"오류 발생 : {e}")

    def login(self):
        self.driver.get('https://etk.srail.kr/cmc/01/selectLoginForm.do')
        WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.ID, 'srchDvNm01')))
        self.driver.find_element(By.ID, 'srchDvNm01').send_keys(str(self.login_id))
        self.driver.find_element(By.ID, 'hmpgPwdCphd01').send_keys(str(self.login_psw))
        self.driver.find_element(By.XPATH, '//*[@id="login-form"]/fieldset/div[1]/div[2]/div[2]/div/div[2]/input').click()
        self.driver.implicitly_wait(15)
        return self.driver

    def check_login(self):
        WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.CLASS_NAME, "my-name")))
        menu_text = self.driver.find_element(By.CLASS_NAME, "my-name").text
        if "환영합니다" in menu_text:
            return True
        else:
            return False

    async def go_search(self):
        # 기차 조회 페이지로 이동
        # self.driver.get('https://etk.srail.kr/hpg/hra/01/selectScheduleList.do')
        self.driver.implicitly_wait(15)

        # 출발지 입력
        elm_dpt_stn = self.driver.find_element(By.ID, 'dptRsStnCdNm')
        elm_dpt_stn.clear()
        elm_dpt_stn.send_keys(self.dpt_stn)

        # 도착지 입력
        elm_arr_stn = self.driver.find_element(By.ID, 'arvRsStnCdNm')
        elm_arr_stn.clear()
        elm_arr_stn.send_keys(self.arr_stn)

        # 출발 날짜 입력
        elm_dpt_dt = self.driver.find_element(By.ID, "dptDt")
        self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_dpt_dt)
        Select(elm_dpt_dt).select_by_value(self.dpt_dt)

        # 출발 시간 입력
        elm_dpt_tm = self.driver.find_element(By.ID, "dptTm")
        self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_dpt_tm)
        Select(elm_dpt_tm).select_by_visible_text(self.dpt_tm)
        
        # 경로우대권 적용
        if self.want_senior:
            elm_psg_adult = self.driver.find_element(By.ID, "psgInfoPerPrnb1")
            elm_psg_elder = self.driver.find_element(By.ID, "psgInfoPerPrnb4")
            self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_psg_adult)
            self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_psg_elder)
            Select(elm_psg_adult).select_by_index(0)
            Select(elm_psg_elder).select_by_index(1)

        # 동반 어린이 적용
        if self.want_child:
            elm_psg_adult = self.driver.find_element(By.ID, "psgInfoPerPrnb1")
            elm_psg_child = self.driver.find_element(By.ID, "psgInfoPerPrnb5")
            self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_psg_adult)
            self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_psg_child)
            Select(elm_psg_adult).select_by_index(1)
            Select(elm_psg_child).select_by_index(1)
        
        # elm_psg_child = self.driver.find_element_by_name("psgInfoPerPrnb5")
        # self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_psg_child)
        # Select(self.driver.find_element_by_name("psgInfoPerPrnb5")).select_by_value(self.psg_child)
        if self.cnt_refresh == 0:
            print("============================")
            config_txt = (f'기차를 조회합니다\n'
                          f'출발역:{self.dpt_stn} , 도착역:{self.arr_stn}\n'
                          f'날짜:{self.dpt_dt}, 시간: {self.real_dpt_tm}시 이후\n'
                          f'{self.num_trains_to_check}개의 기차 중 예약\n'
                          f'예약 대기 사용: {self.want_reserve}\n'
                          f'특실 여부: {self.want_special}\n'
                          f'무조건 여부: {self.want_any}\n'
                          f'경로우대 여부: {self.want_senior}')
            print(config_txt)
            # print("기차를 조회합니다")
            # print(f"출발역:{self.dpt_stn} , 도착역:{self.arr_stn}\n날짜:{self.dpt_dt}, 시간: {self.real_dpt_tm}시 이후\n{self.num_trains_to_check}개의 기차 중 예약")
            # # print(f"출발역:{self.dpt_stn} , 도착역:{self.arr_stn}\n날짜:{self.dpt_dt}, 시간: {self.dpt_tm}시 이후\n성인: {self.psg_adult}매, 아동: {self.psg_child}매\n{self.num_trains_to_check}개의 기차 중 예약")
            # print(f"예약 대기 사용: {self.want_reserve}")
            # print(f"특실 여부: {self.want_special}")
            # print(f"무조건 여부: {self.want_any}")
            if self.notify:
                print("----------------------------")
                print("텔레그램 test 메시지 전송")
                print("메시지 안오면 확인 후 재실행")
                await self.telegram_send(txt=config_txt)
            print("============================")

        # 조회하기 버튼 클릭
        self.driver.find_element(By.XPATH, "//input[@value='조회하기']").click()
        try:
            # Wait until Netfunnel is not present
            netfunnel = self.driver.find_element(By.ID, "NetFunnel_Loading_Popup")
            print("NetFunnel 감지, 우회 시도")
            if not self.NF_pass_flag:
                wait = WebDriverWait(self.driver, 1800)
                element = wait.until(EC.staleness_of(netfunnel))
                for request in self.driver.requests:
                    if request.response:
                        if "nf.letskorail" and "opcode=5004" in request.url:
                                key_idx0 = request.url.index("key=")
                                key_idx1 = request.url.index("&nfid")
                                self.key = request.url[key_idx0+4:key_idx1]
                                self.NF_pass_flag = True
                                print(f'{request.url}, 응답코드 {request.response.status_code}, 컨텐츠 유형: {request.response.headers["Content-Type"]}')
                                print("Token : " + self.key)
            time.sleep(1)
        except StaleElementReferenceException:
            self.driver.implicitly_wait(30)
        except NoSuchElementException:
            self.driver.implicitly_wait(3)

        while True:
            max_num_train = 1
            try:
                tbody = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody")
                tr = tbody.find_elements(By.TAG_NAME, "tr")
                max_num_train = len(tr)
                self.num_trains_to_check = min(max_num_train, self.num_trains_to_check)
            except NoSuchElementException:
                submit = self.driver.find_element(By.XPATH, "//input[@value='조회하기']")
                self.driver.execute_script("arguments[0].click();", submit)
                try:
                    # Wait until Netfunnel is not present
                    NetFunnel = self.driver.find_element(By.ID, "NetFunnel_Loading_Popup")
                    print("NetFunnel 감지, 우회 시도")
                    if self.NF_pass_flag:
                        self.driver.execute_script("javascript:NetFunnel.gLastData.key='" + self.key + "'")
                    wait = WebDriverWait(self.driver, 1800)
                    element = wait.until(EC.staleness_of(NetFunnel))
                    time.sleep(1)

                    self.driver.implicitly_wait(30)
                except TimeoutException:
                    self.driver.implicitly_wait(30)
                except StaleElementReferenceException:
                    self.driver.implicitly_wait(3)
                except NoSuchElementException:
                    self.driver.implicitly_wait(3)

            if self.dpt_tm != self.real_dpt_tm:
                for idx in range(0, max_num_train):
                    dpt = self.driver.find_element(By.CSS_SELECTOR,f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({1 + idx}) > td:nth-child(4)").text
                    dpt_time = dpt.split('\n')[1]
                    hour = dpt_time.split(':')[0]
                    if hour == self.real_dpt_tm:
                        self.dpt_tm_offset = idx
                        break
            else:
                self.dpt_tm_offset = 0

            for i in range(1, self.num_trains_to_check + 1):
                try:
                    tr = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i + self.dpt_tm_offset})")
                    special_seat = tr.find_element(By.CSS_SELECTOR, "td:nth-child(6)").text
                    standard_seat = tr.find_element(By.CSS_SELECTOR, "td:nth-child(7)").text
                    reservation = tr.find_element(By.CSS_SELECTOR, "td:nth-child(8)").text
                except StaleElementReferenceException:
                    special_seat = "매진"
                    standard_seat = "매진"
                    reservation = "매진"
                except NoSuchElementException:
                    submit = self.driver.find_element(By.XPATH, "//input[@value='조회하기']")
                    self.driver.execute_script("arguments[0].click();", submit)
                    try:
                        # Wait until Netfunnel is not present
                        NetFunnel = self.driver.find_element(By.ID, "NetFunnel_Loading_Popup")
                        print("NetFunnel 감지, 우회 시도")
                        if self.NF_pass_flag:
                            self.driver.execute_script("javascript:NetFunnel.gLastData.key='" + self.key + "'")
                        wait = WebDriverWait(self.driver, 1800)
                        element = wait.until(EC.staleness_of(NetFunnel))
                        time.sleep(1)
                        self.driver.implicitly_wait(30)
                    except TimeoutException:
                        self.driver.implicitly_wait(30)
                    except StaleElementReferenceException:
                        self.driver.implicitly_wait(3)
                    except NoSuchElementException:
                        self.driver.implicitly_wait(3)
                
                if self.want_special or self.want_any:
                    if "예약하기" in special_seat:
                        print("예약 가능 클릭")

                        # Error handling in case that click does not work
                        try:
                            self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i + self.dpt_tm_offset}) > td:nth-child(6) > a").click()
                        except ElementClickInterceptedException as err:
                            print(err)
                            self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i + self.dpt_tm_offset}) > td:nth-child(6) > a").send_keys(Keys.ENTER)
                        finally:
                            self.driver.implicitly_wait(3)

                        # 예약이 성공하면
                        if self.driver.find_elements(By.ID, 'isFalseGotoMain'):
                            self.cnt_quantity += 1
                            result_msg = str(self.cnt_quantity) + "/" + str(self.quantity) + " 번째 티켓"
                            print(result_msg)
                            print("일반실 예약 성공")
                            booked_tm_dpt = self.driver.find_element(By.CSS_SELECTOR, f"#list-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr > td:nth-child(6)")
                            booked_tm_arr = self.driver.find_element(By.CSS_SELECTOR, f"#list-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr > td:nth-child(7)")
                            result_str = "출발시간 : " + booked_tm_dpt.text + " / 도착시간 : " + booked_tm_arr.text
                            print(result_str)
                            # if self.notify:
                            #     asyncio.run(self.telegram_send(txt=result_msg))
                            #     asyncio.run(self.telegram_send(txt="특실 예약 성공!"))
                            #     asyncio.run(self.telegram_send(txt=result_str))
                            if (self.cnt_quantity == self.quantity):
                                self.is_booked = True
                                break
                            else:
                                self.driver.back()  # 뒤로가기
                                self.driver.implicitly_wait(5)
                        else:
                            print("특실 잔여석 없음. 다시 검색")
                            self.driver.back()  # 뒤로가기
                            try:
                                # Wait until Netfunnel is not present
                                NetFunnel = self.driver.find_element(By.ID, "NetFunnel_Loading_Popup")
                                print("NetFunnel 감지, 우회 시도")
                                if self.NF_pass_flag:
                                    self.driver.execute_script("javascript:NetFunnel.gLastData.key='" + self.key + "'")
                                wait = WebDriverWait(self.driver, 1800)
                                element = wait.until(EC.staleness_of(NetFunnel))
                                time.sleep(1)

                            except TimeoutException:
                                self.driver.implicitly_wait(3)
                            except StaleElementReferenceException:
                                self.driver.implicitly_wait(3)
                            except NoSuchElementException:
                                self.driver.implicitly_wait(3)

                if ((not self.want_special) or self.want_any) and "예약하기" in standard_seat:
                   print("예약 가능 클릭")

                   # Error handling in case that click does not work
                   try:
                       wait = WebDriverWait(self.driver, 5)
                       element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i + self.dpt_tm_offset}) > td:nth-child(7) > a")))
                       self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i + self.dpt_tm_offset}) > td:nth-child(7) > a").click()
                   except ElementClickInterceptedException as err:
                       print(err)
                       self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i + self.dpt_tm_offset}) > td:nth-child(7) > a").send_keys(Keys.ENTER)
                   finally:
                       self.driver.implicitly_wait(3)

                   # 예약이 성공하면
                   if self.driver.find_elements(By.ID, 'isFalseGotoMain'):
                       self.cnt_quantity += 1
                       result_msg = str(self.cnt_quantity) + "/" + str(self.quantity) + " 번째 티켓"
                       print(result_msg)
                       print("일반실 예약 성공")
                       booked_tm_dpt = self.driver.find_element(By.CSS_SELECTOR, f"#list-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr > td:nth-child(6)")
                       booked_tm_arr = self.driver.find_element(By.CSS_SELECTOR, f"#list-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr > td:nth-child(7)")
                       result_str ="출발시간 : " + booked_tm_dpt.text + " / 도착시간 : " + booked_tm_arr.text
                       print(result_str)
                       train_info = self.driver.find_element(By.CSS_SELECTOR, f"#list-form > fieldset > div:nth-child(6) > table > tbody > tr > td:nth-child(3)")
                       print(train_info.text)
                       # self.bot.sendMessage(chat_id=self.chat_id, text=result_msg)
                       # self.bot.sendMessage(chat_id=self.chat_id, text="일반실 예약 성공!")
                       # self.bot.sendMessage(chat_id=self.chat_id, text=result_str)
                       # self.bot.sendMessage(chat_id=self.chat_id, text=train_info.text)
                       result_msg_merge = f'{result_msg} \n일반실 예약 성공! \n{result_str} \n{train_info.text}'
                       # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                       # asyncio.run(self.telegram_send(result_msg_merge))
                       if self.notify:
                           await self.telegram_send(txt=result_msg_merge)
                       if(self.cnt_quantity == self.quantity):
                           self.is_booked = True
                           break
                       else:
                           self.driver.back()  # 뒤로가기
                           self.driver.implicitly_wait(5)
                   else:
                       print("일반실 잔여석 없음. 다시 검색")
                       self.driver.back()  # 뒤로가기
                       try:
                           # Wait until Netfunnel is not present
                           NetFunnel = self.driver.find_element(By.ID, "NetFunnel_Loading_Popup")
                           print("NetFunnel 감지, 우회 시도")
                           if self.NF_pass_flag:
                               self.driver.execute_script("javascript:NetFunnel.gLastData.key='" + self.key + "'")
                           wait = WebDriverWait(self.driver, 1800)
                           element = wait.until(EC.staleness_of(NetFunnel))
                           time.sleep(1)
                           self.driver.implicitly_wait(30)
                       except TimeoutException:
                           self.driver.implicitly_wait(3)
                       except StaleElementReferenceException:
                           self.driver.implicitly_wait(3)
                       except NoSuchElementException:
                           self.driver.implicitly_wait(3)

                if self.want_reserve:
                    if "신청하기" in reservation:
                        print("예약 대기 완료")
                        self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i + self.dpt_tm_offset}) > td:nth-child(8) > a").click()
                        self.is_booked = True
                        self.cnt_quantity += 1
                        result_msg = str(self.cnt_quantity) + "/" + str(self.quantity) + " 번째 티켓"
                        print(result_msg)
                        booked_tm_dpt = self.driver.find_element(By.CSS_SELECTOR, f"#list-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr > td:nth-child(6)")
                        booked_tm_arr = self.driver.find_element(By.CSS_SELECTOR, f"#list-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr > td:nth-child(7)")
                        result_str = "출발시간 : " + booked_tm_dpt.text + " / 도착시간 : " + booked_tm_arr.text
                        print(result_str)
                        # if self.notify:
                        #     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                        #     asyncio.run(self.telegram_send(txt=result_msg))
                        #     asyncio.run(self.telegram_send(txt="일반실 예약 대기 예약 성공!"))
                        #     asyncio.run(self.telegram_send(txt=result_str))
                        if (self.cnt_quantity == self.quantity):
                            self.is_booked = True
                            break
                        else:
                            self.driver.back()  # 뒤로가기
                            self.driver.implicitly_wait(5)

            if not self.is_booked:
                print("예약 불가")
                time.sleep(0.5 + random() * 0.5)  # 0.5~1초 랜덤으로 기다리기
                self.cnt_refresh += 1
                print(f"새로고침 {self.cnt_refresh}회")

                # if self.cnt_refresh % 200 == 0 and self.cnt_refresh != 0:
                #     current_handle = self.driver.current_window_handle
                #     self.driver.execute_script("window.open('https://etk.srail.kr/hpg/hra/01/selectScheduleList.do');")
                #     element = WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.XPATH, "//input[@value='조회하기']")))
                #     self.driver.switch_to.window(current_handle)
                #     self.driver.close()
                #     self.driver.switch_to.window(self.driver.window_handles[-1])

                # 다시 조회하기
                try:
                    submit = self.driver.find_element(By.XPATH, "//input[@value='조회하기']")
                    self.driver.execute_script("arguments[0].click();", submit)
                except NoSuchElementException:
                    self.driver.refresh()
                    submit = self.driver.find_element(By.XPATH, "//input[@value='조회하기']")
                    self.driver.execute_script("arguments[0].click();", submit)

                # Wait until Netfunnel is not present
                try:
                    # Wait until Netfunnel is not present
                    NetFunnel = self.driver.find_element(By.ID, "NetFunnel_Loading_Popup")
                    print("NetFunnel 감지, 우회 시도")
                    if self.NF_pass_flag:
                        self.driver.execute_script("javascript:NetFunnel.gLastData.key='" + self.key + "'")
                    wait = WebDriverWait(self.driver, 1800)
                    element = wait.until(EC.staleness_of(NetFunnel))
                except TimeoutException:
                    self.driver.implicitly_wait(30)
                except StaleElementReferenceException:
                    self.driver.implicitly_wait(3)
                except NoSuchElementException:
                    self.driver.implicitly_wait(3)
            else:
                print("예약 완료")
                return True
    # TODO
    #def pay(self):

    def run(self, login_id, login_psw):
        result = False
        self.run_driver()
        login_check = False
        while not login_check:
            self.set_log_info(login_id, login_psw)
            self.login()
            login_check = self.check_login()
            if not login_check:
                print("로그인 실패. 다시 시도함.")
            else:
                print("로그인 성공!")
        self.driver.get('https://etk.srail.kr/hpg/hra/01/selectScheduleList.do')
        asyncio.run(self.go_search())
        # while not result:
        #     asyncio.run(self.refresh_search_result())
        self.driver.quit()