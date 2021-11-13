#!/usr/bin/python
import logging
import argparse
import re
import requests
from bs4 import BeautifulSoup as bs
from tqdm import tqdm
from urllib.parse import urlparse,urlunparse

headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:93.0) Gecko/20100101 Firefox/93.0"}
download_pat = re.compile("download\W*\(\d+p\W*mp4\)", re.IGNORECASE)
quality_pat = re.compile("\d+p", re.IGNORECASE)
logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_gogo(vid_link):

    stream = requests.get(vid_link, headers=headers)
    stream_sp = bs(stream.text, features="lxml")
    try:
        gog_lnk=stream_sp.iframe.get("src").replace("streaming.php", "download")
    except AttributeError:
        return None
    gog = requests.get(gog_lnk, headers=headers)
    referer=gog.url
    gog_sp = bs(gog.text, features="lxml")
    links = gog_sp.find_all("a")
    # valid download links
    q_links = [lnk for lnk in links if download_pat.fullmatch(lnk.text)]
    try:
        lnk_dct = {quality_pat.search(lnk.text).group():lnk.get("href") for lnk in q_links}
    except AttributeError:
        return None
    return (referer, lnk_dct)

def download_gogo(link, referer=None):
    # this redirects to another which should not be followed but to go to location lnk manually
    r_resp = requests.get(link, allow_redirects=False, headers=headers)
    headers["referer"] = "https://gogoplay1.com/"
    r_lnk = r_resp.headers.get("Location")
    flname = r_lnk.split("?")[0].split("/")[-1]
    with requests.get(r_lnk, headers=headers, stream=True) as r:
         r.raise_for_status()
         file_size = int(r.headers.get('Content-Length', 0))
         bar = tqdm(total=file_size, unit='iB', unit_scale=True)
         with open(flname, "wb") as f:
             for chunk in r.iter_content(chunk_size=8192):
                 bar.update(len(chunk))
                 f.write(chunk)
         bar.close
    headers.pop("referer")

def set_verbosity(level, quite=False):
    if quite:
        log_level= logging.ERROR
    elif level == 1:
        log_level = logging.INFO
    elif level >= 2:
        log_level = logging.DEBUG
    else:
        log_level = logging.WARN
    logging.basicConfig(level=log_level)

def download(link):
    logging.debug(f"[video] {link}")
    referer, gogo_lnk = get_gogo(link)
    download_gogo( gogo_lnk.get("360P"), referer=referer)

def parse_playlist(link):
    url = urlparse(link)
    logging.debug(f"[playlist] {link}")
    resp = requests.get(link, headers=headers)
    logging.debug(f"playlist response {resp.status_code}")
    sp = bs(resp.text, features="lxml")
    results = sp.find("div", attrs={"class":"listing listing8515 full"})
    paths = [ anch.get("href") for anch in results.find_all("a")]
    return [ urlunparse(url._replace(path=path)) for path in paths[::-1]]

    
def is_playlist(link):
    url = urlparse(link)
    if url.path.startswith("/category"):
        return 0
    elif url.path.startswith("/watch"):
        return 1
    else:
        logging.debug(f"found link {link}")
        return 2

def args_init():
    parser = argparse.ArgumentParser(description="Downloads single kissanimes episode or whole playlist")
    parser.add_argument("links", metavar="LINK", nargs="+", help="kissanime individual episode links or whole playlist links")

    logging_grp = parser.add_mutually_exclusive_group()
    logging_grp.add_argument("-v", "--verbose", action="count", dest="verbose", default=0, help="verbose level use -vvv for debug level")
    logging_grp.add_argument("-q", "--quite", action="store_true", dest="quite", help="disables all logging except error messages")

    type_flag = parser.add_mutually_exclusive_group(required=False)
    type_flag.add_argument("-p", "--playlist", action="store_true", dest="is_playlist", help="if set considers given link as playlist")
    type_flag.add_argument("-s", "--single", action="store_true", dest="is_link", help="considers given link as a single  vid link")

    parser.add_argument( "--start-index", dest="start_index", default=0, type=int, help="starting index of the video in a playlist. (starts with 0 and start index file will be downloaded)")

    indx_cnt = parser.add_mutually_exclusive_group(required=False)
    indx_cnt.add_argument( "--end-index", dest="end_index", default=None, type=int,  help="starting index of the video in a playlist. (starts with 0 and start index file will be downloaded)")
    indx_cnt.add_argument("-c",  "--count", dest="count", default=None, type=int,  help="number of videos in playlist to download")

    return parser.parse_args()


if __name__ == "__main__":
    args = args_init()
    set_verbosity(args.verbose)
    dl_links = []
    if args.is_link:
        dl_links = args.links
    elif args.is_playlist:
        for link in args.links:
            dl_links.extend(parse_playlist(link))
    else:
        for link in args.links:
            pl = is_playlist(link)
            if  pl == 0:
                dl_links.extend(parse_playlist(link))
            elif pl == 1 :
               dl_links.append(link)
            else:
                logging.warning("Couldn't detect url. is it valid url?")
    # since count and end are add_mutually_exclusive_groups no need to check else condition
    if args.count is None:
        end = args.end_index
    elif args.start_index:
        end = args.start_index + args.count
    else:
        end = args.count
    logging.debug(f"list range {args.start_index}:{end}")
    for lnk in dl_links[args.start_index:end]:
        download(lnk)

