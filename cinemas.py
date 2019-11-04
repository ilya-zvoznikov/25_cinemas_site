from bs4 import BeautifulSoup
import requests
import logging
from fake_useragent import UserAgent
import sys
from threading import Thread
import copy
import json
import re
from xml.etree import ElementTree

AFISHA_URL = 'https://www.afisha.ru{}'
AFISHA_FILMS_URL = 'https://www.afisha.ru/novosibirsk/schedule_cinema/'
AFISHA_PARAMS = {'view': 'list'}

KINOPOISK_RATING = 'https://rating.kinopoisk.ru/{}.xml'
KINOPOISK_URL = 'https://www.kinopoisk.ru{}'
KINOPOISK_PARAMS = {
    'level': '7',
    'from': 'forma',
    'result': 'adv',
    'm_act[from]': 'forma',
    'm_act[what]': 'content',
    'm_act[find]': '',
    'm_act[year]': '',
}


def getCinemasLogger():
    logging.basicConfig(
        filename='cinemas.log',
        level=logging.DEBUG,
        filemode='w',
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    )
    cinemasLogger = logging.getLogger('CinemasLogger')
    return cinemasLogger


def fetch_page(url, user_agent, params=None):
    try:
        response = requests.get(
            url,
            headers={'User-Agent': user_agent},
            params=params,
            timeout=10,
        )
        return response.text, response.url
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.ConnectTimeout,
        requests.exceptions.ReadTimeout,
    ):
        return


def parse_afisha_list(raw_html):
    pattern = r'React.createElement\(__desktopComponents.Widget,(.+}})\),document.getElementById'
    afisha_dict = json.loads(re.findall(pattern, raw_html)[0])
    movies = afisha_dict['widget']['Items']
    return movies


def fetch_movie_id(raw_html, url):
    try:
        if 'index.php' in url:
            soup = BeautifulSoup(raw_html, 'html.parser')
            element_most_wanted = soup.find('div',
                                            {'class': 'element most_wanted'})
            movie_url = element_most_wanted.find('p', {'class': 'name'}).a[
                'href']
            movie_id = re.findall('/level/1/film/(\d+)/sr/1/', movie_url)[0]
        else:
            movie_id = re.findall('.+//www.kinopoisk.ru/film/(\d+).*', url)[0]
    except (AttributeError, ValueError) as e:
        logger.error(e)
        return
    if not movie_id:
        return
    return movie_id


def fetch_movie_rating(movie_id):
    response = requests.get(KINOPOISK_RATING.format(movie_id))
    root = ElementTree.fromstring(response.content)
    movie_rating = root.find('kp_rating').text
    return float(movie_rating)


def output_movies_to_console(movies):
    for movie in sorted(movies, key=lambda m: m['kp_rating'], reverse=True):
        if movie['kp_rating'] == 0:
            rating = 'Рейтинг недоступен (мало оценок)'
        else:
            rating = movie['kp_rating']
        print('{} / {}'.format(movie['Name'], rating))


class CinemaThread(Thread):
    def __init__(self, movie, logger):
        Thread.__init__(self)
        self.movie = movie
        self.params = copy.copy(KINOPOISK_PARAMS)
        self.useragent = UserAgent().random
        self.logger = logger

    def run(self):
        self.params['m_act[find]'] = self.movie['Name']
        self.params['m_act[year]'] = self.movie['ProductionYear']
        kinopoisk_raw_html, kinopoisk_movie_url = fetch_page(
            url=KINOPOISK_URL.format('/index.php'),
            user_agent=self.useragent,
            params=self.params,
        )

        if not kinopoisk_raw_html:
            self.logger.error(
                'Error page "{}" fetching'.format(self.movie['Name'])
            )
            return
        else:
            self.logger.info(
                'Page "{}" fetched'.format(self.movie['Name'])
            )
        movie_id = fetch_movie_id(
            kinopoisk_raw_html,
            kinopoisk_movie_url,
        )
        self.movie['kp_url'] = KINOPOISK_URL.format('/film/' + movie_id)
        self.movie['kp_rating'] = fetch_movie_rating(movie_id)
        if not self.movie['kp_rating']:
            self.logger.error(
                "Error {}'s rating fetching".format(self.movie['Name'])
            )
        else:
            self.logger.info(
                'Movie "{}" rating fetched'.format(self.movie['Name'])
            )
        return self.movie


def get_movies():
    logger = getCinemasLogger()
    logger.info('Script started')
    user_agent = UserAgent()
    afisha_raw_html, afisha_url = fetch_page(
        url=AFISHA_FILMS_URL,
        user_agent=user_agent.random,
        params=AFISHA_PARAMS,
    )

    if not afisha_raw_html:
        message = 'No info at Afisha.ru or connection error'
        logger.error('Script finished with "{}"'.format(message))
        sys.exit(message)
    else:
        logger.info("Afisha's content loaded")

    movies = parse_afisha_list(afisha_raw_html)
    if not movies:
        message = 'No movies today'
        logger.error('Script finished with "{}"'.format(message))
        sys.exit(message)
    else:
        logger.info('Movies names list fetched')
    threads = []
    for movie in movies:
        thread = CinemaThread(movie, logger)
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
    logger.info('Script finished')
    for movie in movies:
        movie['MovieScheduleUrl'] = AFISHA_URL.format(
            movie['MovieScheduleUrl'],
        )
    return movies


if __name__ == '__main__':
    print(get_movies())
