"""Offline regression tests replacing the obsolete scripts.* live-network tests."""

import pandas as pd
from fantasyfootball.parsers.html_parser import HTMLParser
from fantasyfootball.datasources.profootballreference import (
    ProFootballReferenceDataSource,
)
from fantasyfootball.transformers.profootballreference_transformer import (
    GameByGameTransformer,
)


def test_player_ids_and_links():
    parser = HTMLParser()
    parser.set_content(
        '<table id="fantasy"><tr><td><a href="/players/M/McCaCh01.htm">Christian</a></td></tr></table>'
    )
    parser.parse()
    source = ProFootballReferenceDataSource(parser=parser)
    assert source._extract_player_hrefs("fantasy") == ["/players/M/McCaCh01.htm"]
    assert source._player_id_transform("/players/M/McCaCh01.htm") == ("M", "McCaCh01")


def test_weekly_transform_preserves_fumbles_and_home_away():
    data = pd.DataFrame(
        {"1": ["@", None], "fumbles_fmb": [2, 0], "fumbles_fl": [1, 0], "week": [1, 2]}
    )
    result = GameByGameTransformer().transform(data)
    assert result["home/away"].tolist() == ["Away", "Home"]
    assert result.fumbles.tolist() == [2, 0]
    assert result.fumbles_lost.tolist() == [1, 0]


def test_comment_wrapped_table():
    parser = HTMLParser()
    parser.set_content(
        '<div><!-- <table id="stats"><tr><td>3</td></tr></table> --></div>'
    )
    parser.parse()
    assert len(parser.extract("table", id="stats")) == 1
