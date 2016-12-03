import urllib2
import json
import datetime
import csv
import time
import os
import argparse


def request_until_succeed(url):
    req = urllib2.Request(url)
    success = False
    response = None
    while success is False:
        try:
            response = urllib2.urlopen(req)

            if response.getcode() == 200:
                success = True
        except Exception as e:
            print(e)
            time.sleep(5)
            print("Error for URL %s: %s" % (url, datetime.datetime.now()))
            print("Retrying.")

    return response.read()

    # Needed to write tricky unicode correctly to csv


def unicode_normalize(text):
    return text.translate({0x2018: 0x27, 0x2019: 0x27, 0x201C: 0x22, 0x201D: 0x22,
                           0xa0: 0x20}).encode('utf-8')


def getFacebookGroupFeedData(group_id, access_token, num_statuses):
    # Construct the URL string; see
    # http://stackoverflow.com/a/37239851 for Reactions parameters
    base = "https://graph.facebook.com/v2.8"
    node = "/%s/feed" % group_id
    fields = "/?fields=message,link,created_time,type,name,id," + \
             "comments.limit(0).summary(true),shares,reactions." + \
             "limit(0).summary(true),from,picture,story"
    parameters = "&limit=%s&access_token=%s" % (num_statuses, access_token)
    url = base + node + fields + parameters

    # retrieve data
    data = json.loads(request_until_succeed(url))
    return data


def getReactionsForStatus(status_id, access_token):
    # See http://stackoverflow.com/a/37239851 for Reactions parameters
    # Reactions are only accessable at a single-post endpoint

    base = "https://graph.facebook.com/v2.8"
    node = "/%s" % status_id
    reactions = "/?fields=" \
                "reactions.type(LIKE).limit(0).summary(total_count).as(like)" \
                ",reactions.type(LOVE).limit(0).summary(total_count).as(love)" \
                ",reactions.type(WOW).limit(0).summary(total_count).as(wow)" \
                ",reactions.type(HAHA).limit(0).summary(total_count).as(haha)" \
                ",reactions.type(SAD).limit(0).summary(total_count).as(sad)" \
                ",reactions.type(ANGRY).limit(0).summary(total_count).as(angry)"
    parameters = "&access_token=%s" % access_token
    url = base + node + reactions + parameters

    # retrieve data
    data = json.loads(request_until_succeed(url))

    return data


def processFacebookGroupFeedStatus(status, access_token):
    # The status is now a Python dictionary, so for top-level items,
    # we can simply call the key.

    # Additionally, some items may not always exist,
    # so must check for existence first
    status_id = status['id']
    status_message = '' if 'message' not in status.keys() else \
        unicode_normalize(status['message'])
    link_name = '' if 'name' not in status.keys() else \
        unicode_normalize(status['name'])
    status_type = status['type']
    status_link = '' if 'link' not in status.keys() else \
        unicode_normalize(status['link'])
    status_author = unicode_normalize(status['from']['name'])

    # Time needs special care since a) it's in UTC and
    # b) it's not easy to use in statistical programs.

    status_published = datetime.datetime.strptime(
        status['created_time'], '%Y-%m-%dT%H:%M:%S+0000')
    status_published = status_published + datetime.timedelta(hours=-5)  # EST
    # best time format for spreadsheet programs:
    status_published = status_published.strftime('%Y-%m-%d %H:%M:%S')

    # Nested items require chaining dictionary keys.

    num_reactions = 0 if 'reactions' not in status else \
        status['reactions']['summary']['total_count']
    num_comments = 0 if 'comments' not in status else \
        status['comments']['summary']['total_count']
    num_shares = 0 if 'shares' not in status else \
        status['shares']['count']

    # Counts of each reaction separately; good for sentiment
    # Only check for reactions if past date of implementation:
    # http://newsroom.fb.com/news/2016/02/reactions-now-available-globally/

    reactions = getReactionsForStatus(status_id, access_token) \
        if status_published > '2016-02-24 00:00:00' else {}

    num_likes = 0 if 'like' not in reactions else \
        reactions['like']['summary']['total_count']

    # Special case: Set number of Likes to Number of reactions for pre-reaction
    # statuses

    num_likes = num_reactions if status_published < '2016-02-24 00:00:00' else \
        num_likes

    def get_num_total_reactions(reaction_type, reactions):
        if reaction_type not in reactions:
            return 0
        else:
            return reactions[reaction_type]['summary']['total_count']

    num_loves = get_num_total_reactions('love', reactions)
    num_wows = get_num_total_reactions('wow', reactions)
    num_hahas = get_num_total_reactions('haha', reactions)
    num_sads = get_num_total_reactions('sad', reactions)
    num_angrys = get_num_total_reactions('angry', reactions)

    """
    invoke single post
    """
    try:
        picture = status['picture']
    except KeyError:
        picture = None

    # return a tuple of all processed data
    post_link = ' https://www.facebook.com/groups/chaseshelloutofthekaroo/permalink/' + status_id.split('_')[1]
    return (post_link, status_id, status_author, status_type,
            status_link, status_published, num_reactions, num_comments,
            num_shares, num_likes, num_loves, num_wows, num_hahas, num_sads,
            num_angrys, picture, link_name)


def scrapeFacebookGroupFeedStatus(group_id, access_token, path):
    csv_file = os.path.join(path + '%s_facebook_statuses.csv' % group_id)
    with open(csv_file, 'w') as file:
        w = csv.writer(file)
        w.writerow(["post_link", "post_id", "status_author",
                    "status_type", "status_link",
                    "status_published", "num_reactions", "num_comments",
                    "num_shares", "num_likes", "num_loves", "num_wows",
                    "num_hahas", "num_sads", "num_angrys", "picture", "link_name"])

        has_next_page = True
        num_processed = 0  # keep a count on how many we've processed
        scrape_starttime = datetime.datetime.now()
        print("\nScraping %s Facebook Page: %s\n" %
              (group_id, scrape_starttime))

        statuses = getFacebookGroupFeedData(group_id, access_token, 100)

        while has_next_page:
            for status in statuses['data']:
                # Ensure it is a status with the expected metadata
                if 'reactions' in status:
                    w.writerow(processFacebookGroupFeedStatus(status,
                                                             access_token))

                # output progress occasionally to make sure code is not
                # stalling
                num_processed += 1
                if num_processed % 100 == 0:
                    print("%s Statuses Processed: %s" % (num_processed,
                                                         datetime.datetime.now()))

            # if there is no next page, we're done.
            if 'paging' in statuses.keys():
                statuses = json.loads(request_until_succeed(
                    statuses['paging']['next']))
            else:
                has_next_page = False
        print("\nDone!\n%s Statuses Processed in %s" %
              (num_processed, datetime.datetime.now() - scrape_starttime))


def get_id(name, token):
    base = "https://graph.facebook.com/v2.8/search?q="
    node = "%s" % name
    fb_type = "&type=group"

    url = base + node + fb_type + "&access_token=" + token
    return json.loads(request_until_succeed(url))

"""
Page
"""


def getFacebookPageFeedData(page_id, access_token, num_statuses):
    # Construct the URL string; see http://stackoverflow.com/a/37239851 for
    # Reactions parameters
    base = "https://graph.facebook.com/v2.8"
    node = "/%s/posts" % page_id
    fields = "/?fields=message,link,created_time,type,name,id," + \
             "comments.limit(0).summary(true),shares,reactions" + \
             ".limit(0).summary(true)"
    parameters = "&limit=%s&access_token=%s" % (num_statuses, access_token)
    url = base + node + fields + parameters

    # retrieve data
    data = json.loads(request_until_succeed(url))

    return data


def processFacebookPageFeedStatus(status, access_token):

    # The status is now a Python dictionary, so for top-level items,
    # we can simply call the key.

    # Additionally, some items may not always exist,
    # so must check for existence first

    status_id = status['id']
    status_message = '' if 'message' not in status.keys() else \
            unicode_normalize(status['message'])
    link_name = '' if 'name' not in status.keys() else \
            unicode_normalize(status['name'])
    status_type = status['type']
    status_link = '' if 'link' not in status.keys() else \
            unicode_normalize(status['link'])

    # Time needs special care since a) it's in UTC and
    # b) it's not easy to use in statistical programs.

    status_published = datetime.datetime.strptime(
            status['created_time'],'%Y-%m-%dT%H:%M:%S+0000')
    status_published = status_published + \
            datetime.timedelta(hours=-5) # EST
    status_published = status_published.strftime(
            '%Y-%m-%d %H:%M:%S') # best time format for spreadsheet programs

    # Nested items require chaining dictionary keys.

    num_reactions = 0 if 'reactions' not in status else \
            status['reactions']['summary']['total_count']
    num_comments = 0 if 'comments' not in status else \
            status['comments']['summary']['total_count']
    num_shares = 0 if 'shares' not in status else status['shares']['count']

    # Counts of each reaction separately; good for sentiment
    # Only check for reactions if past date of implementation:
    # http://newsroom.fb.com/news/2016/02/reactions-now-available-globally/

    reactions = getReactionsForStatus(status_id, access_token) if \
            status_published > '2016-02-24 00:00:00' else {}

    num_likes = 0 if 'like' not in reactions else \
            reactions['like']['summary']['total_count']

    # Special case: Set number of Likes to Number of reactions for pre-reaction
    # statuses

    num_likes = num_reactions if status_published < '2016-02-24 00:00:00' \
            else num_likes

    def get_num_total_reactions(reaction_type, reactions):
        if reaction_type not in reactions:
            return 0
        else:
            return reactions[reaction_type]['summary']['total_count']

    num_loves = get_num_total_reactions('love', reactions)
    num_wows = get_num_total_reactions('wow', reactions)
    num_hahas = get_num_total_reactions('haha', reactions)
    num_sads = get_num_total_reactions('sad', reactions)
    num_angrys = get_num_total_reactions('angry', reactions)

    # Return a tuple of all processed data

    return (status_id, status_message, link_name, status_type, status_link,
            status_published, num_reactions, num_comments, num_shares,
            num_likes, num_loves, num_wows, num_hahas, num_sads, num_angrys)


def scrapeFacebookPageFeedStatus(page_id, access_token, path):
    csv_file = os.path.join(path + '%s_facebook_statuses.csv' % page_id)
    with open(csv_file, 'w') as file:
        w = csv.writer(file)
        w.writerow(["status_id", "status_message", "link_name", "status_type",
                    "status_link", "status_published", "num_reactions",
                    "num_comments", "num_shares", "num_likes", "num_loves",
                    "num_wows", "num_hahas", "num_sads", "num_angrys"])

        has_next_page = True
        num_processed = 0   # keep a count on how many we've processed
        scrape_starttime = datetime.datetime.now()

        print("Scraping %s Facebook Page: %s\n" % (page_id, scrape_starttime))

        statuses = getFacebookPageFeedData(page_id, access_token, 100)

        while has_next_page:
            for status in statuses['data']:

                # Ensure it is a status with the expected metadata
                if 'reactions' in status:
                    w.writerow(processFacebookPageFeedStatus(status,
                                                             access_token))

                # output progress occasionally to make sure code is not
                # stalling
                num_processed += 1
                if num_processed % 100 == 0:
                    print("%s Statuses Processed: %s" %
                          (num_processed, datetime.datetime.now()))

            # if there is no next page, we're done.
            if 'paging' in statuses.keys():
                statuses = json.loads(request_until_succeed(
                    statuses['paging']['next']))
            else:
                has_next_page = False

        print("\nDone!\n%s Statuses Processed in %s" %
              (num_processed, datetime.datetime.now() - scrape_starttime))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', '-n', help='Group or page name')
    parser.add_argument('--path', '-p', help='Path')
    parser.add_argument('--type', '-t', help='Type can be group or page')
    parser.add_argument('--app_id', '-i', help='Facebook app id')
    parser.add_argument('--app_secret', '-s', help='Facebook app secret')

    namespace = parser.parse_args()
    entity_id = None

    if namespace.app_id is None or namespace.app_secret is None:
        app_id = "596940707173430"
        app_secret = "b7222a0e0715416397b8bfae7fb7c595"
    else:
        app_id = namespace.app_id
        app_secret = namespace.app_secret

    if namespace.path is not None:
        # check path
        if os.path.isdir(namespace.path) is True:
            path = namespace.path + '/'
        else:
            print('Path not exist. Will save to current directory')
            path = ''
    else:
        path = ''

    access_marker = 'EAAIe6hbNlDYBAIBbNGu0fflZCZAZBiDRctkS49fzMfaquZCGqjHx665rafO4KuwKycNYSFKKrUSyJtBuYGaQI0' \
                    'ic2GTuflrfalsviVBfXGh5T4W0zBeNvhdXOemDLPDJ7ZANBAaG3P1RXwvFcAobbMGq3cFbhhIQZD'
    access_token = app_id + "|" + app_secret

    if namespace.name.isdigit() is False:
        # try get an id
        data = get_id(namespace.name, access_marker)
        try:
            entity_id = data['data'][0].get('id')

            if entity_id is None:
                print('Page or group not found!')
        except IndexError:
            print('Page or group not found!')
    else:
        entity_id = namespace.name

    if entity_id is not None:
        if namespace.type is not None and namespace.type == 'group':
                scrapeFacebookGroupFeedStatus(entity_id, access_token, path)
        elif namespace.type is not None and namespace.type == 'page':
            scrapeFacebookPageFeedStatus(entity_id, access_token, path)
        else:
            print('Required parameter --type empty or none! Please adjust it.')
