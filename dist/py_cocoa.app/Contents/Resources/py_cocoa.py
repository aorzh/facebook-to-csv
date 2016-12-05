from Cocoa import *
from Foundation import NSObject
import urllib2
import json
import datetime
import csv
import time
import os
import thread


class PythonClassForCocoa(NSWindowController):
    counterTextField = objc.IBOutlet()

    def windowDidLoad(self):
        NSWindowController.windowDidLoad(self)


class MWController(NSObject):
    textField = objc.IBOutlet()
    selectBox = objc.IBOutlet()
    appId = objc.IBOutlet()
    appSecret = objc.IBOutlet()
    messages = objc.IBOutlet()
    results = []

    @objc.IBAction
    def run_(self, sender):
        entity_id = None
        name_value = self.textField.stringValue()
        type_value = self.selectBox.indexOfSelectedItem()

        path = ''
        if self.appId.stringValue() == '' or self.appSecret.stringValue() == '':
            app_id = "596940707173430"
            app_secret = "b7222a0e0715416397b8bfae7fb7c595"

        else:
            app_id = self.appId.stringValue()
            app_secret = self.appSecret.stringValue()

        access_marker = 'EAAIe6hbNlDYBAIBbNGu0fflZCZAZBiDRctkS49fzMfaquZCGqjHx665rafO4KuwKycNYSFKKrUSyJtBuYGaQI0' \
                        'ic2GTuflrfalsviVBfXGh5T4W0zBeNvhdXOemDLPDJ7ZANBAaG3P1RXwvFcAobbMGq3cFbhhIQZD'
        access_token = app_id + "|" + app_secret

        if name_value.isdigit() is False:
            # try get an id
            data = self.get_id(name_value, access_marker)
            try:
                entity_id = data['data'][0].get('id')

                if entity_id is None:
                    self.messages.textStorage().mutableString().appendString_(u'\nPage or group not found!')
                    self.setNeedsDisplay_(True)
            except IndexError:
                self.messages.textStorage().mutableString().appendString_(u'\nPage or group not found!')
                self.setNeedsDisplay_(True)
        else:
            entity_id = name_value
        NSLog('EID: ' + entity_id)
        if entity_id is not None:
            if type_value is not None and type_value == 1:
                thread.start_new_thread(self.scrapeFacebookGroupFeedStatus, (entity_id, access_token, path))
            elif type_value is not None and type_value == 0:
                thread.start_new_thread(self.scrapeFacebookPageFeedStatus, (entity_id, access_token, path))

        """
        Do parsing below (need move it to separate file)
        """

    def request_until_succeed(self, url):
        req = urllib2.Request(str(url))
        success = False
        response = None
        # NSLog('URL ' + url)
        while success is False:
            try:
                response = urllib2.urlopen(req)

                if response.getcode() == 200:
                    success = True
            except Exception as e:
                print(e)
                time.sleep(5)
                self.messages.textStorage().mutableString().appendString_(
                    u"\nError for URL %s: %s" % (url, datetime.datetime.now()))
                self.messages.textStorage().mutableString().appendString_(u"\nRetrying.")
                self.setNeedsDisplay_(True)

        return response.read()

        # Needed to write tricky unicode correctly to csv

    def unicode_normalize(self, text):
        return text.translate({0x2018: 0x27, 0x2019: 0x27, 0x201C: 0x22, 0x201D: 0x22,
                               0xa0: 0x20}).encode('utf-8')

    def getFacebookGroupFeedData(self, group_id, access_token, num_statuses):
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
        data = json.loads(self.request_until_succeed(url))
        return data

    def getReactionsForStatus(self, status_id, access_token):
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
        data = json.loads(self.request_until_succeed(url))

        return data

    def processFacebookGroupFeedStatus(self, status, access_token):
        # The status is now a Python dictionary, so for top-level items,
        # we can simply call the key.

        # Additionally, some items may not always exist,
        # so must check for existence first
        status_id = status['id']
        status_message = '' if 'message' not in status.keys() else \
            self.unicode_normalize(status['message'])
        link_name = '' if 'name' not in status.keys() else \
            self.unicode_normalize(status['name'])
        status_type = status['type']
        status_link = '' if 'link' not in status.keys() else \
            self.unicode_normalize(status['link'])
        status_author = self.unicode_normalize(status['from']['name'])

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

        reactions = self.getReactionsForStatus(status_id, access_token) \
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

        # invoke single post

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

    def scrapeFacebookGroupFeedStatus(self, group_id, access_token, path):

        csv_file = os.path.join(path + '%s_facebook_statuses.csv' % group_id)
        with open(csv_file, 'w') as f:
            w = csv.writer(f)
            w.writerow(["post_link", "post_id", "status_author",
                        "status_type", "status_link",
                        "status_published", "num_reactions", "num_comments",
                        "num_shares", "num_likes", "num_loves", "num_wows",
                        "num_hahas", "num_sads", "num_angrys", "picture", "link_name"])

            has_next_page = True
            num_processed = 0  # keep a count on how many we've processed
            scrape_starttime = datetime.datetime.now()
            self.messages.textStorage().mutableString().appendString_(u"\nScraping %s Facebook Page: %s\n" %
                                                                      (group_id, scrape_starttime))
            self.messages.textStorage().mutableString().displayIfNeeded_()
            statuses = self.getFacebookGroupFeedData(group_id, access_token, 100)

            while has_next_page:
                for status in statuses['data']:
                    # Ensure it is a status with the expected metadata
                    if 'reactions' in status:
                        w.writerow(self.processFacebookGroupFeedStatus(status,
                                                                       access_token))

                    # output progress occasionally to make sure code is not
                    # stalling
                    num_processed += 1
                    if num_processed % 100 == 0:
                        self.messages.mutableString().appendString_(
                            u"\n%s Statuses Processed: %s" % (num_processed,
                                                              datetime.datetime.now()))
                        self.messages.textStorage().setNeedsDisplay_(True)

                # if there is no next page, we're done.
                if 'paging' in statuses.keys():
                    statuses = json.loads(self.request_until_succeed(
                        statuses['paging']['next']))
                else:
                    has_next_page = False
            self.messages.textStorage().mutableString().appendString_(u"\nDone!\n%s Statuses Processed in %s" %
                                                                      (num_processed,
                                                                       datetime.datetime.now() - scrape_starttime))
            self.setNeedsDisplay_(True)

    def get_id(self, name, token):
        base = "https://graph.facebook.com/v2.8/search?q="
        node = "%s" % name
        fb_type = "&type=group"

        url = base + node + fb_type + "&access_token=" + token
        return json.loads(self.request_until_succeed(url))

    """
    Page
    """

    def getFacebookPageFeedData(self, page_id, access_token, num_statuses):
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
        data = json.loads(self.request_until_succeed(url))

        return data

    def processFacebookPageFeedStatus(self, status, access_token):

        # The status is now a Python dictionary, so for top-level items,
        # we can simply call the key.

        # Additionally, some items may not always exist,
        # so must check for existence first

        status_id = status['id']
        status_message = '' if 'message' not in status.keys() else \
            self.unicode_normalize(status['message'])
        link_name = '' if 'name' not in status.keys() else \
            self.unicode_normalize(status['name'])
        status_type = status['type']
        status_link = '' if 'link' not in status.keys() else \
            self.unicode_normalize(status['link'])

        # Time needs special care since a) it's in UTC and
        # b) it's not easy to use in statistical programs.

        status_published = datetime.datetime.strptime(
            status['created_time'], '%Y-%m-%dT%H:%M:%S+0000')
        status_published = status_published + datetime.timedelta(hours=-5)  # EST
        status_published = status_published.strftime(
            '%Y-%m-%d %H:%M:%S')  # best time format for spreadsheet programs

        # Nested items require chaining dictionary keys.

        num_reactions = 0 if 'reactions' not in status else \
            status['reactions']['summary']['total_count']
        num_comments = 0 if 'comments' not in status else \
            status['comments']['summary']['total_count']
        num_shares = 0 if 'shares' not in status else status['shares']['count']

        # Counts of each reaction separately; good for sentiment
        # Only check for reactions if past date of implementation:
        # http://newsroom.fb.com/news/2016/02/reactions-now-available-globally/

        reactions = self.getReactionsForStatus(status_id, access_token) if \
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

    def scrapeFacebookPageFeedStatus(self, page_id, access_token, path):
        csv_file = os.path.join(path + '%s_facebook_statuses.csv' % page_id)
        with open(csv_file, 'w') as f:
            w = csv.writer(f)
            w.writerow(["status_id", "status_message", "link_name", "status_type",
                        "status_link", "status_published", "num_reactions",
                        "num_comments", "num_shares", "num_likes", "num_loves",
                        "num_wows", "num_hahas", "num_sads", "num_angrys"])

            has_next_page = True
            num_processed = 0  # keep a count on how many we've processed
            scrape_starttime = datetime.datetime.now()

            self.messages.textStorage().mutableString().appendString_(
                u"\nScraping %s Facebook Page: %s\n" % (page_id, scrape_starttime))
            self.messages.setNeedsDisplay_(True)

            statuses = self.getFacebookPageFeedData(page_id, access_token, 100)

            while has_next_page:
                for status in statuses['data']:

                    # Ensure it is a status with the expected metadata
                    if 'reactions' in status:
                        w.writerow(self.processFacebookPageFeedStatus(status,
                                                                      access_token))

                    # output progress occasionally to make sure code is not
                    # stalling
                    num_processed += 1
                    if num_processed % 100 == 0:
                        self.messages.textStorage().mutableString().appendString_(u"\n%s Statuses Processed: %s" %
                                                                                  (num_processed,
                                                                                   datetime.datetime.now()))
                        self.messages.setNeedsDisplay_(True)

                # if there is no next page, we're done.
                if 'paging' in statuses.keys():
                    statuses = json.loads(self.request_until_succeed(
                        statuses['paging']['next']))
                else:
                    has_next_page = False

            self.messages.textStorage().mutableString().appendString_(u"\nDone!\n%s Statuses Processed in %s" %
                                                                      (num_processed,
                                                                       datetime.datetime.now() - scrape_starttime))
            self.setNeedsDisplay_(True)

if __name__ == "__main__":
    app = NSApplication.sharedApplication()

    # Initiate the contrller with a XIB
    viewController = PythonClassForCocoa.alloc().initWithWindowNibName_("CocoaWindow")

    # Show the window
    viewController.showWindow_(viewController)

    # Bring app to top
    NSApp.activateIgnoringOtherApps_(True)

    from PyObjCTools import AppHelper

    AppHelper.runEventLoop()
