import os
import re
import sys
import time
# import pickle
import numpy as np
import pandas as pd

# Scrapping
from bs4 import BeautifulSoup
from selenium import webdriver
from user_agent import generate_user_agent
# from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.common.alert import Alert
from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
# from selenium.webdriver.common.action_chains import ActionChains
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.common.exceptions import UnexpectedAlertPresentException, NoAlertPresentException, NoSuchElementException, TimeoutException

# Exception Error Handling
import socket
import warnings
warnings.filterwarnings("ignore")

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    root = sys._MEIPASS
else:
    cur_dir = os.path.dirname(os.path.realpath(__file__))
    root = os.path.abspath(os.path.join(cur_dir, os.pardir, os.pardir))
    src = os.path.abspath(os.path.join(cur_dir, os.pardir))
    sys.path.append(src)
    
try:
    from hangle import _distance
except:
    pass

'''TLS CA error solution'''
def override_where():
    """ overrides certifi.core.where to return actual location of cacert.pem """
    # change this to match the location of cacert.pem
    return os.path.join(root, '_certifi', 'cacert.pem')

def replace_certifi():
    if hasattr(sys, "frozen"):
        import certifi.core

        os.environ["REQUESTS_CA_BUNDLE"] = override_where()
        certifi.core.where = override_where

        # delay importing until after where() has been replaced
        import requests.utils
        import requests.adapters
        # replace these variables in case these modules were
        # imported before we replaced certifi.core.where
        requests.utils.DEFAULT_CA_BUNDLE_PATH = override_where()
        requests.adapters.DEFAULT_CA_BUNDLE_PATH = override_where()

def get_url(url, window=None, image=None):
    ''' Set up webdriver, useragent & Get url '''
    
    wd = None
    socket.setdefaulttimeout(30)
    error = []
    attempts = 0 # url parsing ????????????
    # 10??? ?????? parsing ????????? pass
    while attempts < 10:
        try:  
            attempts += 1
            # user agent
            options = Options() 
            userAgent = generate_user_agent(os=('mac', 'linux'), navigator='chrome', device_type='desktop')
            options.add_argument('window-size=1920x1080')
            options.add_argument("--disable-gpu")
            options.add_argument('--disable-extensions')
            if window == None:
                options.add_argument('headless')
            if image == None:
                options.add_argument('--blink-settings=imagesEnabled=false')
            options.add_argument(f'user-agent={userAgent}')

            # web driver 
            wd = webdriver.Chrome(ChromeDriverManager().install(), chrome_options=options)
            wd.get(url)
            wd.implicitly_wait(5)
            break

        # ????????????
        except Exception as e:
            print(f'\n\nError: {str(e)}\n\n')
            
            # tls ca error solution
            if 'TLS CA' in str(e):
                replace_certifi()
            
            time.sleep(300)
            try:
                wd.quit()
            except:
                pass
            wd = None
    return wd
    
def scroll_down(wd, sleep_time, check_count):
    ''' page scroll down '''
    
    cnt = 0
    while True:
        height = wd.execute_script("return document.body.scrollHeight")
        wd.find_element_by_tag_name('body').send_keys(Keys.END)
        time.sleep(sleep_time)
        cnt += 1
        if cnt == check_count:
            break        
    return wd

def scraper_nv(product_id, search_word):
    ''' ????????? ???????????? ????????????????????? ????????? ???????????? ?????? ?????? ???????????????
    ::Input data::
    - product_id: ?????? ?????? id
    - search_word: ??????????????? ????????? 
    
    ::Output data::
    - scraps: ?????????????????? ?????? ?????? ?????????
    - status: ??????????????? ?????? ?????? (-1: ?????? ??????????????? ??????(defalt), 0: ???????????? ??????, 1: ???????????? ??????
    '''
    
    input_data = search_word.replace('[??????]', '') # '[??????]' ?????? 
    input_txt = re.sub(r'[\(\)\{\}\[\]\/]', ' ', input_data) # bracket ??????
    input_txt_ = re.sub(r' +', ' ', input_txt).strip() # ?????? ?????? ??????
    input_keyword = input_txt_.replace(' ','%20') # ?????? ??? ?????????
    # set up url 
    url = f'https://search.shopping.naver.com/search/all?&frm=NVSHCAT&origQuery={input_keyword}%20%20%20-??????%20-??????%20-set%20-Set%20-SET%20-?????????%20-?????????%20-Package%20-PACKAGE&pagingIndex=1&pagingSize=40&productSet=model&query={input_keyword}&sort=rel&timestamp=&viewType=list&xq=??????%20??????%20set%20Set%20SET%20?????????%20?????????%20Package%20PACKAGE'

    # get url 
    wd = get_url(url)
    if wd == None:
        scraps = []
        status = -1 # status when parsing url fails
    
    else:
        # scroll down
        # scroll_down(wd)
        html = wd.page_source
        soup = BeautifulSoup(html,'lxml') 
        item_divs = soup.find_all('div',class_='basicList_inner__eY_mq')
        scraps = []
        
        if len(item_divs) == 0:
            pass
        
        else:
            cnt = 0
            for item_div in item_divs:

                # product name
                product_name = item_div.find('div',class_='basicList_title__3P9Q7').text 

                # ????????? ????????? ????????? ?????? (levenshtein distance ??????)
                # input ?????? title??? 50%?????? ???????????? ?????? 
                word_0 = input_txt_.replace(' ', '')
                word_1 = product_name.replace(' ', '')
                cost = _distance.jamo_levenshtein(word_0, word_1)
                max_len = max(len(word_0), len(word_1))
                sim = (max_len - cost) / max_len
                
                if '??????' not in product_name and '??????' not in product_name:
                    # product_url
                    product_url = item_div.find('a')['href']

                    # price
                    if item_div.find('span',class_='price_num__2WUXn') != None:
                        price = item_div.find('span',class_='price_num__2WUXn').text 
                    else:
                        price = np.nan

                    # category
                    if item_div.find('div',class_='basicList_depth__2QIie') != None:
                        category = item_div.find('div',class_='basicList_depth__2QIie')
                        category_ = [ctg.text for ctg in category] 

                    # product_description
                    if item_div.find('div',class_='basicList_detail_box__3ta3h') != None:
                        descriptions = item_div.find('div',class_='basicList_detail_box__3ta3h')
                        if descriptions.find('a', class_='basicList_detail__27Krk') != None:
                            descriptions_ = descriptions.text.split('|')
                            desc_dict = {}
                            for desc in descriptions_:
                                key = desc.split(':')[0].replace(' ', '')
                                value = desc.split(':')[1].replace(' ', '')    
                                desc_dict[key] = value
                            product_description = str(desc_dict)

                        elif descriptions.text != '':
                            desc_dict = {}
                            desc = descriptions.text
                            key = desc.split(':')[0].replace(' ', '')
                            value = desc.split(':')[1].replace(' ', '')    
                            desc_dict[key] = value
                            product_description = str(desc_dict)
                        else:
                            product_description = np.nan

                    else:
                        product_description = np.nan

                    # registered_date (?????? ????????? ???????????? ????????? ??????, ???????????? ?????? ????????? ?????? ??? ??? ?????? ??? ?????? ??????)
                    if item_div.find('span',class_='basicList_etc__2uAYO') != None: 
                        registered_date = item_div.find('span',class_='basicList_etc__2uAYO').text
                        registered_date_ = registered_date.split('?????????')[-1].rstrip('.')
                    else:
                        registered_date_ = np.nan

                    # product_reviews_count
                    if item_div.find_all('a',class_='basicList_etc__2uAYO') != []:
                        url_boxes = item_div.find_all('a',class_='basicList_etc__2uAYO')
                        url_box = [x for x in url_boxes if '??????' in x.text]
                        if len(url_box) != 0:
                            product_reviews_count = url_box[0].find('em',class_='basicList_num__1yXM9').text.replace(',', '')
                        else:
                            product_reviews_count = 0
                    else:
                        product_reviews_count = 0

                    # product_rating
                    if item_div.find('span',class_='basicList_star__3NkBn') != None:
                        product_rating = float(item_div.find('span',class_='basicList_star__3NkBn').text.split('??????')[-1])
                    else:
                        product_rating = np.nan

                    # product_store
                    if item_div.find_all('span',class_='basicList_mall_name__1XaKA') != []:
                        product_store = item_div.find_all('span',class_='basicList_mall_name__1XaKA')[0].text # ????????? ?????????
                    else:
                        product_store = np.nan
                    
                    scraps.append([int(product_id), str(input_txt_), str(product_name), str(product_url), str(price), str(category_), str(product_description), str(registered_date_), int(product_reviews_count), float(product_rating), str(product_store), float(round(sim, 4))])
                    cnt += 1
                    
                else:
                    pass
                
                # ?????? ?????? 5??? ?????? ??????
                if cnt == 5:
                    break
            
        wd.quit()
        if len(scraps) == 0:
            status = 0
        else:
            status = 1
            
    return scraps, status