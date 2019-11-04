from flask import Flask, render_template
from flask_caching import Cache
from cinemas import get_movies

config = {
    "DEBUG": True,  # some Flask specific configs
    "CACHE_TYPE": "simple",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": 300
}

app = Flask(__name__)
app.config.from_mapping(config)
cache = Cache(app)


@cache.cached(timeout=600, key_prefix='cached_movies')
def get_cached_movies():
    return sorted(
        get_movies(),
        key=lambda m: m['kp_rating'],
        reverse=True,
    )


movies = get_cached_movies()


@cache.cached(timeout=600)
@app.route('/')
def films_list():
    movies = get_cached_movies()
    return render_template(
        'films_list.html',
        movies=movies,
    )


@cache.cached(timeout=600)
@app.route('/<int:movie_id>')
def film(movie_id):
    movies = get_cached_movies()
    current_movie = {}
    for movie in movies:
        if movie['ID'] == movie_id:
            current_movie = movie
            break
    return render_template(
        'film.html',
        movie=current_movie,
    )


if __name__ == "__main__":
    app.run()
