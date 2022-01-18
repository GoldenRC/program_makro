from pandas import read_csv
import requests
import json
from datetime import datetime
import time
from datetime import datetime, timedelta
import flask_app

class Twt_User:
    def __init__(self, nick, id):
        self.user_name = nick
        self.id = id
        self.user_follows = []
        self.last_status = ''

class Twt_BOT:
    def main_loop(self):
        """
            Pobierz dane użytkownika i w pętli sprawdzaj listę followersów.
            Co 24h aktualizuj zdjęcia profilowe
        """
        self.read_user_data()
        #self.get_users_ids()
        self.update_all_profile_images()
        last_images_update = datetime.now()
        while True:
            tracking_users = flask_app.Following.query.all()
            for user in tracking_users:
                self.get_user_follows(user)
                #self.get_profile_image(user)
                self.delete_old_activity(user)
                time.sleep(62)
            if last_images_update + timedelta(hours=24) < datetime.now():
                self.update_all_profile_images()
                last_images_update = datetime.now()

    def read_user_data(self):
        """
            Odczytaj dane użytkownika potrzebne do autoryzacji z pliku 'user_data.csv' oraz listę
            osób do śledzenia.
        """
        user_data_csv = read_csv('user_data.csv')
        user_data = user_data_csv.iloc[0]
        self.user_tag = user_data['twt_tag']
        self.user_name = user_data['user_name']
        self.passwd = user_data['passwd']
        self.api_key = user_data['api_key']
        self.api_key_secret = user_data['api_key_secret']
        self.bearer = user_data['bearer']
        self.headers = { 'Authorization': 'Bearer ' + self.bearer }

    def add_user_to_db(self, nickname): # do przerobienia
        """
            Sprawdz czy user jest już w bazie, jak nie to wysyłając request do TwitterAPI v2 z nickname konta nowego użytkownika, zapisz jego ID
        """
        same_user = flask_app.Following.query.filter_by(user_name=nickname).first()
        if not same_user:
            print(nickname)
            twt_api_get_ids_url = 'https://api.twitter.com/2/users/by?usernames=' + nickname
            user_info = requests.get(twt_api_get_ids_url, headers=self.headers)
            user_info_json = json.loads(user_info.text)
            print(user_info_json)
            user_info_json = user_info_json["data"][0]
            print(user_info_json)
            print(f'Znaleziony nowy użytkownik: {user_info_json["username"]} | ID: {user_info_json["id"]}')

            new_user = flask_app.Following()
            new_user.user_name = user_info_json["username"]
            new_user.user_id = user_info_json["id"]
            flask_app.db.session.add(new_user)
            self.get_profile_image(new_user)
            flask_app.db.session.commit()
        else:
            print(f'Wprowadzony użytkownik istnieje już w bazie!')
        
        
        """
            Poniżej stara wersja sprawdzająca ID każdego użytkownika w bazie. Na ten moment nie ma to sensu.
            ID usera jest uzupełniane na bieżąco po dodaniu go do bazy.
        """
        # all_users_to_check = flask_app.db.session.query(flask_app.Following.user_name)
        # print(all_users_to_check)
        # print(new_)
        # if new_acc in all_users_to_check:
        #     return
        # if new_acc:
        #     users_to_check = new_acc
        # else:
        #     try: 
        #         users_to_check = self.convert_list_to_str(all_users_to_check[0])
        #         if users_to_check[-1] == ",":
        #             users_to_check = users_to_check[:-1]
        #     except IndexError:
        #         users_to_check = None
        # if users_to_check:
        #     url = 'https://api.twitter.com/2/users/by?usernames=' + users_to_check
        #     users_info = requests.get(url, headers=self.headers)
        #     users_info_json = json.loads(users_info.text)
        #     print(users_info_json)
        #     for user in users_info_json['data']:
        #         print(f'Znaleziony użytkownik: {user["username"]} | ID: {user["id"]}')
        #         if 0 < all_users_to_check.count():
        #             if user["username"] in all_users_to_check[0]:
        #                 break
        #         new_user = flask_app.Following()
        #         new_user.user_name = user["username"]
        #         new_user.user_id = user["id"]
        #         flask_app.db.session.add(new_user)
        #         self.get_profile_image(new_user)
        #         flask_app.db.session.commit()
        # all_users = flask_app.db.session.query(flask_app.Following.user_name, flask_app.Following.user_id).all()    
        # users_without_ids = []
        # for user_name, user_id in all_users:
        #     if not user_id:
        #         users_without_ids.append(user_name)

        # if users_without_ids:
        #     users_without_ids = self.convert_list_to_str(users_without_ids)
        #     twt_api_get_ids_url = 'https://api.twitter.com/2/users/by?usernames=' + users_without_ids
        #     users_info = requests.get(twt_api_get_ids_url, headers=self.headers)
        #     users_info_json = json.loads(users_info.text)
        #     for user in users_info_json['data']:
        #         print(f'Znaleziony użytkownik: {user["username"]} | ID: {user["id"]}')
        #         flask_app.db.session

    def rem_user(self, user_to_rem):
        """
            Usuń użytkownika z listy obserwowanych
        """
        obj_to_rem = flask_app.Following.query.filter_by(user_name=user_to_rem).all()
        #flask_app.db.session.delete(obj_to_rem)
        for obj in obj_to_rem:
            flask_app.db.session.delete(obj)
        flask_app.db.session.commit()

    def get_user_follows(self, user):
        """
            Wyślij request do TwitterAPI v2 sprawdzający listę followanych użytkowników dla wybranego konta.
            Sprawdź czy możliwe jest pobranie danych z kolejnej podstrony followersów za pomocą sprawdzenia
            czy w odpowiedzi jest 'paginantion_token' - jeśli tak -> odwiedzaj kolejne podstrony
            jeśli nie -> przerwij. Zapisuj w tymczasowej liście znalezionych followanych osób. 
            Porównaj listy followanych osób. 
        """
        temp_follows_list = []
        temp_follows_ids_list = []
        url = f'https://api.twitter.com/2/users/{user.user_id}/following?max_results=1000'
        try:
            checked=False
            while not checked:
                user_follows = requests.get(url, headers=self.headers)
                #print(followers_list.text)
                next_page = True
                while next_page:
                    if user_follows.status_code == 429:
                        print(f'[{datetime.now()}] Rate limit... Odczekuję 360sekund')
                        time.sleep(360)
                        continue
                    follows_list_json = json.loads(user_follows.text)
                    follows_json = follows_list_json['data']
                    for follower in follows_json:
                        temp_follows_list.append(follower['username'])
                        temp_follows_ids_list.append(follower['id'])
                    try:
                        pagination_token = follows_list_json['meta']['next_token']
                    except Exception as e:
                        next_page = False
                    else:
                        print(f'[{datetime.now()}] Wczytuję kolejną stronę followanych profili przez: {user.user_name}.')
                        time.sleep(62)
                        url = f'https://api.twitter.com/2/users/{user.user_id}/following?max_results=1000&pagination_token={pagination_token}'
                        user_follows = requests.get(url, headers=self.headers)
                    
                temp_follows_list = list(dict.fromkeys(temp_follows_list))
                temp_follows_ids_list = list(dict.fromkeys(temp_follows_ids_list))
                self.compare_follows(user, temp_follows_list, temp_follows_ids_list)
                checked = True
        except Exception as e:
            print(str(e))

    def compare_follows(self, user, new_list, new_list_ids):
        """
            Porównaj lisy followanych osób. Zapisz różnicę w liście przez operację XOR na liście nowej i starej.
            Wypisz nowe lub usunięte followane osoby.
        """
        user_follows = self.convert_str_to_list(user.user_follows)
        if new_list != user_follows:
            if not user_follows:
                print(f'[{datetime.now()}] Wycztano followy użytkownika {user.user_name}:  {len(new_list)}')
                user.user_last_status = f'Wycztano followy użytkownika {user.user_name}:  {len(new_list)}'
            else:
                follows_diffrence = set(new_list) ^ set(user_follows)
                new_changes_follows_list = []
                new_changes_unfollows_list = []
                for follow in follows_diffrence:
                    if follow in user_follows:
                        new_changes_unfollows_list.append(follow)
                    else:
                        new_changes_follows_list.append(follow)
                if new_changes_follows_list:
                    print(f'[{datetime.now()}] Nowy follow od użytkownika {user.user_name}:  {new_changes_follows_list}')
                    user.user_last_status = f'Nowy follow od użytkownika {user.user_name}:  {new_changes_follows_list}'
                    new_follows_list = self.convert_str_to_list(user.new_follows)
                    new_follows_dates = self.convert_str_to_list(user.follows_date_changes)
                    new_follows_list += new_changes_follows_list

                    now = datetime.now()
                    time_now = now.strftime("%m/%d/%Y %H:%M:%S")
                    for i in range(len(new_changes_follows_list)):
                        new_follows_dates.append(time_now)

                    user.new_follows = self.convert_list_to_str(new_follows_list)
                    user.follows_date_changes = self.convert_list_to_str(new_follows_dates)

                if new_changes_unfollows_list:
                    print(f'[{datetime.now()}] Nowy unfollow od użytkownika {user.user_name}:  {new_changes_unfollows_list}')
                    self.user_last_status = f'Nowy unfollow od użytkownika {user.user_name}:  {new_changes_unfollows_list}'
                    new_unfollows_list = self.convert_str_to_list(user.removed_follows)
                    new_unfollows_dates = self.convert_str_to_list(user.unfollows_date_changes)
                    new_unfollows_list += new_changes_unfollows_list

                    now = datetime.now()
                    time_now = now.strftime("%m/%d/%Y %H:%M:%S")
                    for i in range(len(new_changes_unfollows_list)):
                        new_unfollows_dates.append(time_now)

                    user.removed_follows = self.convert_list_to_str(new_unfollows_list)
                    user.unfollows_date_changes = self.convert_list_to_str(new_unfollows_dates)   

            user_new_list = self.convert_list_to_str(new_list)
            user_new_list_ids = self.convert_list_to_str(new_list_ids)
            user.user_follows = user_new_list
            user.user_follows_ids = user_new_list_ids
        else:
            print(f'[{datetime.now()}] Brak zmian dla użytkownika {user.user_name}')
            user.user_last_status = f'Brak zmian dla użytkownika {user.user_name}'
            
        flask_app.db.session.commit()

    def update_all_profile_images(self):
        tracking_users = flask_app.Following.query.all()
        for user in tracking_users:
            print(f'Aktualizuję zdjęcie profilowe użytkownika{user.user_id}')
            user_obj_req_url = f'https://api.twitter.com/2/users?ids={user.user_id}&user.fields=profile_image_url'
            user_obj = requests.get(user_obj_req_url, headers=self.headers)
            user_obj_json = json.loads(user_obj.text)
            user.user_avatar = user_obj_json['data'][0]['profile_image_url']

    def get_profile_image(self, user):
        if not user.user_avatar:
            user_obj_req_url = f'https://api.twitter.com/2/users?ids={user.user_id}&user.fields=profile_image_url'
            user_obj = requests.get(user_obj_req_url, headers=self.headers)
            user_obj_json = json.loads(user_obj.text)
            user.user_avatar = user_obj_json['data'][0]['profile_image_url']

    def delete_old_activity(self, user):
        follows_date_changes = self.convert_str_to_list(user.follows_date_changes)
        unfollows_date_changes = self.convert_str_to_list(user.unfollows_date_changes)
        new_follows = self.convert_str_to_list(user.new_follows)
        removed_follows = self.convert_str_to_list(user.removed_follows)

        for i, date in enumerate(follows_date_changes):
            date = datetime.strptime(date, "%m/%d/%Y %H:%M:%S")
            if datetime.now() > date + timedelta(hours=24):
                follows_date_changes.pop(i)
                new_follows.pop(i)

        for i, date in enumerate(unfollows_date_changes):
            date = datetime.strptime(date, "%m/%d/%Y %H:%M:%S")
            if datetime.now() > date + timedelta(hours=24):
                unfollows_date_changes.pop(i)
                removed_follows.pop(i)

        user.follows_date_changes = self.convert_list_to_str(follows_date_changes)
        user.unfollows_date_changes = self.convert_list_to_str(unfollows_date_changes)
        user.new_follows = self.convert_list_to_str(new_follows)
        user.removed_follows = self.convert_list_to_str(removed_follows)    

        flask_app.db.session.commit()
        

    def print_followed_users(self):
        all_users_to_check = flask_app.db.session.query(flask_app.Following.user_name)
        for user in all_users_to_check:
            print(user)

    def convert_str_to_list(self, str_list):
        try:
            if str_list[-1] == ",":
                str_list = str_list[:-1]
            user_follows = str_list.split(',')
            return user_follows
        except:
            return []

    def convert_list_to_str(self, list_to_convert):
        str_list = ''
        for item in list_to_convert:
            str_list += item + ','
        return str_list

def main():
    twt_bot = Twt_BOT()
    twt_bot.main_loop()

if __name__ == "__main__":
    main()

        