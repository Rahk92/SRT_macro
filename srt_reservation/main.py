# -*- coding: utf-8 -*-
import os
import time
import telegram
import requests
import asyncio
from random import randint
from datetime import datetime
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import ElementClickInterceptedException, StaleElementReferenceException, WebDriverException, TimeoutException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from srt_reservation.exceptions import InvalidStationNameError, InvalidDateError, InvalidDateFormatError, InvalidTimeFormatError
from srt_reservation.validation import station_list

class SRT:
    def __init__(self, token, chat_id, dpt_stn, arr_stn, dpt_dt, dpt_tm, num_trains_to_check=2, want_reserve=False, want_special=False, want_any=False, quantity=1):
    # def __init__(self, dpt_stn, arr_stn, dpt_dt, dpt_tm, psg_adult=1, psg_child=0, num_trains_to_check=2, want_reserve=False):
        """
        :param dpt_stn: SRT 출발역
        :param arr_stn: SRT 도착역
        :param dpt_dt: 출발 날짜 YYYYMMDD 형태 ex) 20220115
        :param dpt_tm: 출발 시간 hh 형태, 반드시 짝수 ex) 06, 08, 14, ...
        :param num_trains_to_check: 검색 결과 중 예약 가능 여부 확인할 기차의 수 ex) 2일 경우 상위 2개 확인
        :param want_reserve: 예약 대기가 가능할 경우 선택 여부
        :param want_special: 특실 선택 여부
        """
        self.login_id = None
        self.login_psw = None

        self.dpt_stn = dpt_stn
        self.arr_stn = arr_stn
        self.dpt_dt = dpt_dt
        self.dpt_tm = str(int(dpt_tm) // 2 * 2).zfill(2)
        self.dpt_tm_offset = int(dpt_tm) % 2
        self.real_dpt_tm = dpt_tm
        
        # self.psg_adult = psg_adult
        # self.psg_child = psg_child

        self.num_trains_to_check = num_trains_to_check
        self.want_reserve = want_reserve
        self.want_special = want_special
        self.want_any = want_any
        self.driver = None

        self.is_booked = False  # 예약 완료 되었는지 확인용
        self.cnt_refresh = 0  # 새로고침 회수 기록

        self.check_input()
        self.token = token
        self.chat_id = chat_id
        self.quantity = quantity
        self.cnt_quantity = 0

    async def telegram_send(self, txt):
        bot = telegram.Bot(token=self.token)
        await bot.sendMessage(self.chat_id, txt)

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
            self.driver = webdriver.Chrome()
            # self.driver = webdriver.Chrome(executable_path=chromedriver_path)
            # self.driver = webdriver.Chrome(r"F:\Code\Python\srt_reservation-main\chromedriver.exe")
        except WebDriverException:
           # release = "http://chromedriver.storage.googleapis.com/LATEST_RELEASE"
            #version = requests.get(release).text
            service = Service(executable_path=ChromeDriverManager())
            options = Options()
            user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36"
            options.add_argument('user-agent=' + user_agent)
            options.add_argument("lang=ko_KR")
            options.add_argument('headless')
            options.add_argument('window-size=1920x1080')
            options.add_argument("disable-gpu")
            options.add_argument("--no-sandbox")
            self.driver = webdriver.Chrome()
            
            # self.driver = webdriver.Chrome(ChromeDriverManager(version=version).install())


    def login(self):
        self.driver.get('https://etk.srail.co.kr/cmc/01/selectLoginForm.do')

        self.driver.implicitly_wait(15)
        self.driver.find_element(By.ID, 'srchDvNm01').send_keys(str(self.login_id))
        self.driver.find_element(By.ID, 'hmpgPwdCphd01').send_keys(str(self.login_psw))
        self.driver.find_element(By.XPATH, '//*[@id="login-form"]/fieldset/div[1]/div[1]/div[2]/div/div[2]/input').click()
        self.driver.implicitly_wait(5)
        return self.driver

    def check_login(self):
        menu_text = self.driver.find_element(By.CSS_SELECTOR, "#wrap > div.header.header-e > div.global.clear > div").text
        if "환영합니다" in menu_text:
            return True
        else:
            return False



    def go_search(self):

        # 기차 조회 페이지로 이동
        self.driver.get('https://etk.srail.kr/hpg/hra/01/selectScheduleList.do')
        self.driver.implicitly_wait(5)

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
        Select(self.driver.find_element(By.ID, "dptDt")).select_by_value(self.dpt_dt)

        # 출발 시간 입력
        elm_dpt_tm = self.driver.find_element(By.ID, "dptTm")
        self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_dpt_tm)
        Select(self.driver.find_element(By.ID, "dptTm")).select_by_visible_text(self.dpt_tm)
        
        # 인원 입력
        # elm_psg_adult = self.driver.find_element_by_name("psgInfoPerPrnb1")
        # self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_psg_adult)
        # Select(self.driver.find_element_by_name("psgInfoPerPrnb1")).select_by_value(self.psg_adult)
        
        # elm_psg_child = self.driver.find_element_by_name("psgInfoPerPrnb5")
        # self.driver.execute_script("arguments[0].setAttribute('style','display: True;')", elm_psg_child)
        # Select(self.driver.find_element_by_name("psgInfoPerPrnb5")).select_by_value(self.psg_child)

        print("============================")
        print("기차를 조회합니다")
        print(f"출발역:{self.dpt_stn} , 도착역:{self.arr_stn}\n날짜:{self.dpt_dt}, 시간: {self.real_dpt_tm}시 이후\n{self.num_trains_to_check}개의 기차 중 예약")
        # print(f"출발역:{self.dpt_stn} , 도착역:{self.arr_stn}\n날짜:{self.dpt_dt}, 시간: {self.dpt_tm}시 이후\n성인: {self.psg_adult}매, 아동: {self.psg_child}매\n{self.num_trains_to_check}개의 기차 중 예약")
        print(f"예약 대기 사용: {self.want_reserve}")
        print(f"특실 여부: {self.want_special}")
        print(f"무조건 여부: {self.want_any}")
        print("----------------------------")
        print("텔레그램 test 메시지 전송")
        print("메시지 안오면 확인 후 재실행")
        asyncio.run(self.telegram_send(txt="Test"))
        print("============================")

        # 조회하기 버튼 클릭
        self.driver.find_element(By.XPATH, "//input[@value='조회하기']").click()
        try:
            # Wait until Netfunnel is not present
            netfunnel = self.driver.find_element(By.ID, "NetFunnel_Loading_Popup")
            print("NetFunnel 감지, 우회 시도")
            wait = WebDriverWait(self.driver, 300)
            element = wait.until(EC.staleness_of(netfunnel))

            # self.driver.execute_script("javascript:NetFunnel.gControl.next.success({},{data:{}})")
            time.sleep(1)

        except StaleElementReferenceException:
            self.driver.implicitly_wait(30)
        except NoSuchElementException:
            self.driver.implicitly_wait(3)

    def refresh_search_result(self):
        while True:
            # self.driver.find_element(By.CSS_SELECTOR,f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child()")
            for i in range(1, self.num_trains_to_check+1):
                try:
                    # self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child()")
                    special_seat = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i + self.dpt_tm_offset}) > td:nth-child(6)").text
                    standard_seat = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i + self.dpt_tm_offset}) > td:nth-child(7)").text
                    reservation = self.driver.find_element(By.CSS_SELECTOR, f"#result-form > fieldset > div.tbl_wrap.th_thead > table > tbody > tr:nth-child({i + self.dpt_tm_offset}) > td:nth-child(8)").text
                except StaleElementReferenceException:
                    special_seat = "매진"
                    standard_seat = "매진"
                    reservation = "매진"
                
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
                            asyncio.run(self.telegram_send(txt=result_msg))
                            asyncio.run(self.telegram_send(txt="특실 예약 성공!"))
                            asyncio.run(self.telegram_send(txt=result_str))
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
                                wait = WebDriverWait(self.driver, 300)
                                element = wait.until(EC.staleness_of(NetFunnel))
                                time.sleep(1)

                                # self.driver.execute_script("javascript:NetFunnel.gControl.next.success({},{data:{}})")
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
                       asyncio.run(self.telegram_send(txt=result_msg_merge))
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
                           wait = WebDriverWait(self.driver, 300)
                           element = wait.until(EC.staleness_of(NetFunnel))
                           time.sleep(1)

                           # self.driver.execute_script("javascript:NetFunnel.gControl.next.success({},{data:{}})")
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
                        asyncio.run(self.telegram_send(txt=result_msg))
                        asyncio.run(self.telegram_send(txt="일반실 예약 대기 예약 성공!"))
                        asyncio.run(self.telegram_send(txt=result_str))
                        if (self.cnt_quantity == self.quantity):
                            self.is_booked = True
                            break
                        else:
                            self.driver.back()  # 뒤로가기
                            self.driver.implicitly_wait(5)

            if not self.is_booked:
                time.sleep(randint(2, 4))  # 2~4초 랜덤으로 기다리기

                # 다시 조회하기
                submit = self.driver.find_element(By.XPATH, "//input[@value='조회하기']")
                self.driver.execute_script("arguments[0].click();", submit)
                self.cnt_refresh += 1
                print(f"새로고침 {self.cnt_refresh}회")
                # Wait until Netfunnel is not present
                try:
                    # Wait until Netfunnel is not present
                    NetFunnel = self.driver.find_element(By.ID, "NetFunnel_Loading_Popup")
                    print("NetFunnel 감지, 우회 시도")
                    wait = WebDriverWait(self.driver, 300)
                    element = wait.until(EC.staleness_of(NetFunnel))
                    time.sleep(1)
                    # self.driver.execute_script("javascript:NetFunnel.gControl.next.success({},{data:{}})")
                except TimeoutException:
                    self.driver.implicitly_wait(30)
                except StaleElementReferenceException:
                    self.driver.implicitly_wait(3)
                except NoSuchElementException:
                    self.driver.implicitly_wait(3)
            else:
                print("예약 완료")
                self.telegram_send(txt="예약 완료")
                return self.driver
    # TODO
    #def pay(self):

    def run(self, login_id, login_psw):
        self.run_driver()
        self.set_log_info(login_id, login_psw)
        self.login()
        self.go_search()
        self.refresh_search_result()