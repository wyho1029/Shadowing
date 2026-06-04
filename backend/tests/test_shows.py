from app.shows import SHOWS, get_search_query, list_shows


def test_has_expected_shows():
    ids = {s["id"] for s in SHOWS}
    assert {"bojack", "simpsons", "rick_and_morty",
            "family_guy", "south_park", "bobs_burgers"} <= ids


def test_list_shows_returns_id_and_name():
    shows = list_shows()
    assert all("id" in s and "name" in s for s in shows)


def test_get_search_query_known():
    assert get_search_query("bojack") == "BoJack Horseman best scenes"


def test_get_search_query_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        get_search_query("not_a_show")
