from datetime import datetime, timedelta
import pandas as pd
from pandas.io.parsers import read_csv
import requests
from bs4 import BeautifulSoup
from traceback import format_exc
import json
from os import path
import time
from urllib3 import exceptions

class Product():
    def __init__(self, index, ean, net_price, gross_price, vat):
        self.index = index
        self.ean = ean
        self.net_price = net_price
        self.gross_price = gross_price
        self.vat = vat
        self.price_change = False
        self.vat_change = False
        self.stock = 0

    def __str__(self):
        return f'Indeks: {self.index} | EAN: {self.ean}'

    def __repr__(self):
        return f'Indeks: {self.index} | EAN: {self.ean}'

    def check_price(self, new_net_price, new_gross_price):
        if float(self.net_price) != float(new_net_price):
            self.price_change = True
            self.net_price = new_net_price
        if float(self.gross_price != float(new_gross_price)):
            self.price_change = True
            self.gross_price = new_gross_price

    def check_vat(self, new_vat):
        if float(self.vat) != float(new_vat):
            self.vat_change = True
            self.vat = new_vat

    def set_stock(self, stock):
        self.stock = stock

    def as_dict(self):
        return {
            'index': [self.index],
            'ean': [self.ean],
            'net_price': [self.net_price],
            'gross_price': [self.gross_price],
            'vat': [self.vat],
            'stock': [self.stock],
            'price_change': [self.price_change],
            'vat_change': [self.vat_change]
        }

class Stock_Checker():
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36',
            'sec-ch-ua':'"Chromium";v="94", "Google Chrome";v="94", ";Not A Brand";v="99"',
            'Connection':'keep-alive',
        }
        self.main_page_url = 'https://sso.infinite.pl/auth/realms/InfiniteEH/protocol/openid-connect/auth?client_id=ehurtownia-panel-frontend&redirect_uri=https%3A%2F%2Fmakro.ehurtownia.pl%2Fone%2F%3Fredirect_fragment%3D%252F&response_mode=fragment&response_type=code&scope=openid'
        self.get_token_url = 'https://sso.infinite.pl/auth/realms/InfiniteEH/protocol/openid-connect/token'
        self.product_page_url = 'https://makro.ehurtownia.pl/one/eh-one-backend/rest/1053/8/110100/oferta/%s/karta-towaru?lang=PL'
        self.query_url = 'https://makro.ehurtownia.pl/one/eh-one-backend/rest/1053/8/110100/oferta?lang=PL&offset=0&limit=10&sortAsc=nazwa&cechaWartosc=%s %s'
        self.start_hours = []

    def set_login_credentials(self):
        try:
            with open('makro_user.txt') as user_cfg:
                self.user_username = user_cfg.readline()
                self.user_pwd = user_cfg.readline()
        except:
            print('BŁĄD PLIKU ZAWIERAJĄCEGO DANE DO LOGOWANIA')
            print(format_exc())  

    def set_session(self, session, headers):
        self.session = session
        self.headers = headers

    def save_err(self, err):
        with open('error_checker_log.txt', 'a') as error_log:
            print('Zapisuję błąd...')
            error_log.write(err)

    def restart_session(self):
        print('Odświeżam sesję...')
        self.session = requests.Session()
        self.headers = {
            'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36',
            'sec-ch-ua':'"Chromium";v="94", "Google Chrome";v="94", ";Not A Brand";v="99"',
            'Connection':'keep-alive',
        }       

    def auth_user(self):
        attempt = 0
        while attempt < 7:
            print('Autoryzuję użytkownika...')
            try:
                main_page = self.session.get(self.main_page_url, headers=self.headers)
                parsed_page = BeautifulSoup(main_page.text, 'html.parser')
                form = parsed_page.find('form', attrs={'id':"kc-form-login"})
                login_url = form['action']
                login_data = {'username': self.user_username, 'password': self.user_pwd, 'credentialId': ''}

                auth_user = self.session.post(login_url, headers=self.headers, data=login_data, allow_redirects=True)
                try:
                    code_index = (auth_user.url).find('code') + len('code') + 1
                    print('Użytkownik zalogowany pomyślnie!\nUzyskuję kod autoryzacyjny...')
                    auth_code = (auth_user.url)[code_index:]
                except:
                    print('Niepoprawne dane logowania!')
                    self.save_err(format_exc())
                    attempt += 1
                    time.sleep(2)
                else:
                    auth_data = {
                        'code': auth_code,
                        'grant_type': 'authorization_code',
                        'client_id': 'ehurtownia-panel-frontend',
                        'redirect_uri': 'https://makro.ehurtownia.pl/one/?redirect_fragment=%2F'
                    }

                    token_page = requests.post(self.get_token_url, headers=self.headers, data=auth_data)
                    resp = json.loads(token_page.text)
                    acc_token = resp['access_token']
                    self.headers['Authorization'] = 'Bearer '+ acc_token
                    print('Token autoryzacyjny został pomyślnie uzyskany!\n')
            except TypeError:
                print('Błąd autoryzacji użytkownika!')
                print('Czekam 60 sekund...')
                attempt += 1
                time.sleep(60)
                self.restart_session()
            except:
                print('Błąd autoryzacji użytkownika!')
                print('Czekam 60 sekund...')
                self.save_err(format_exc())
                attempt += 1
                time.sleep(60)
                self.restart_session()
            else:
                break


    def check_stock(self, product):
        attempt = 0
        while attempt < 5:
            product_details = ''
            print('Sprawdzam aktualność danych dla produktu', product)
            try:
                query_result = self.session.get((self.query_url % (product.index, product.ean)), headers=self.headers, timeout=15)
                product_details = json.loads(query_result.text)
                product_details = product_details['pozycje'][0]
                vat = product_details['procVat']
                try:
                    net_price = product_details['cenaNettoJedn']
                    gross_price = product_details['cenaBruttoJedn']
                except:
                    net_price = product_details['cenaNetto']
                    gross_price = product_details['cenaBrutto']

                product.check_price(net_price, gross_price)
                product.check_vat(vat)
            except IndexError:
                if attempt < 3:
                    attempt += 1
                else:
                    print('Produkt niedostępny.')
                    product.set_stock(0)
                    break
            
            except (exceptions.ConnectTimeoutError, ConnectionResetError, NameError,requests.exceptions.Timeout,requests.exceptions.ConnectionError, TimeoutError, exceptions.ProtocolError, exceptions.MaxRetryError, exceptions.NewConnectionError, requests.exceptions.ChunkedEncodingError):
                print('Błąd połączenia')
                attempt += 1
                time.sleep(10)
            except:
                if any(x in query_result.text for x in ('INTERNAL_ERROR', 'Unable to authenticate', 'Unauthorized', 'Whitelabel Error Page')):
                    self.auth_user()
                elif product_details:
                    print('Błąd!')
                    self.save_err(format_exc())
                    attempt += 1
                time.sleep(4)
            else:
                product.set_stock(100)
                return

    def start_bot(self):
        self.set_login_credentials()
        self.auth_user()

    def save_product(self, product, first_run):
        print('Dodaję produkt do bazy danych')
        product_df = pd.DataFrame(product.as_dict())
        if path.exists('produkty_sprawdzone.csv') == False or first_run:
            product_df.to_csv('produkty_sprawdzone.csv', index=False, mode='w', header=True)
        else: 
            product_df.to_csv('produkty_sprawdzone.csv', index=False, mode='a', header=False)

    def set_timer(self):
        try:
            with open('godziny_sprawdzen.txt', 'r') as check_hours:
                check_hours = check_hours.readlines()
                for hour in check_hours:
                    hour = hour.replace('\n','')
                    hour, minute = hour.split(':')
                    self.start_hours.append([hour, minute])
        except Exception as e:
            print(e)
            print('Błąd pliku txt z godzinami')

        # while True:
        #     #try:
        #     timer_input = input('Wpisz godzinę sprawdzania (HH:MM) lub "x" aby zakończyć wpisywanie: ')
        #     if 'x' in timer_input:
        #         break
        #     hour, minute = timer_input.split(':')
        #     self.start_hours.append([hour, minute])
        #     #except:
        #     #print('Niepoprawne wejście! Spróbuj jeszcze raz.')

    def check_time(self, print_hours=False):
        if print_hours:
            print('Czekam...')
            print('Godziny sprawdzeń:', end=" ")
        for hour in self.start_hours:
            if print_hours:
                print(hour[0]+":"+hour[1]+", ", end=" ")
            if int(hour[0]) == datetime.now().hour:
                if int(hour[1]) == datetime.now().minute:  
                    return True
        return False

def check_output(starting_df, output_df):
    if not starting_df['index'].equals(output_df['index']):
        uncommon_rows = pd.concat([starting_df, output_df]).drop_duplicates(subset='ean', keep=False)
        return uncommon_rows
    return pd.DataFrame()



def main():
    main_bot = Stock_Checker()
    main_bot.set_timer()
    saved_products = pd.read_csv('produkty.csv')

    while True:
        main_bot.start_bot()
        first_run = True
        products = saved_products.copy()
        
        while not products.empty:
            print(products)
            for i, prd in products.iterrows():
                try:
                    product = Product(prd['index'], prd['ean'], prd['net_price'], prd['gross_price'], prd['vat'])
                    main_bot.check_stock(product)
                except:
                    print('Błąd!')
                    main_bot.save_err(f'Błąd main: {prd["index"]}')
                    main_bot.save_err(format_exc())
                main_bot.save_product(product, first_run)
                first_run = False
            
            print('Sprawdzam czy wszystkie produkty zostały poprawnie sprawdzone...')
            if path.exists('produkty_sprawdzone.csv'):
                output_products = pd.read_csv('produkty_sprawdzone.csv')
                products = check_output(saved_products, output_products)
            

        print('Czekam 60 sekund po sprawdzeniu...')
        time.sleep(10)

        start = False
        while not start:
            start = main_bot.check_time(print_hours=True)
            if start:
                break
            print(' ')
            time.sleep(5)

if __name__=="__main__":
    main()