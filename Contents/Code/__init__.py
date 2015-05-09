import urllib, urllib2, base64

# Const
VERSION  = '0.1.1'
ART      = 'art-default.png'
ICON     = 'icon-default.png'
PREFIX   = '/video/oz'
HOST     = 'api.oz.com'
WAYPOINT = 'https://'+HOST+'/v1/'
AGENT    = 'OZ.bundle '+VERSION+' (Plex Media Server)'
X_SECRET = 'b89b0060-cece-11e3-b6e1-7f4ae3f97677'
X_TOKEN  = 'ozmobileandroid'


####################################################################################################
def Start():

	Log('Starting OZ (version %s)', VERSION)
	ObjectContainer.title1 = 'OZ'
	Dict['auth_error'] = None

	if 'access_token' not in Dict:
		GetSession()


####################################################################################################
def Request(Path):
	url = WAYPOINT + Path
	request = {}
	headers = {}
	headers['User-Agent'] = AGENT
	headers['x-application-secret'] = X_SECRET
	headers['x-application-token'] = X_TOKEN
	headers["Authorization"] = "Bearer " + Dict['access_token']
	body = urllib2.urlopen(urllib2.Request(url, None, headers)).read()
	response = JSON.ObjectFromString(body)

	return response


####################################################################################################
def GetSession():
	u = Prefs['username']
	p = Prefs['password']
	url = WAYPOINT + 'authorizations'
	request = {}
	headers = {}
	headers['User-Agent'] = AGENT
	headers['x-application-secret'] = X_SECRET
	headers['x-application-token'] = X_TOKEN
	if (u and p):
		headers["Authorization"] = "Basic %s" % (base64.encodestring("%s:%s" % (u, p))[:-1])
		try:
			body = urllib2.urlopen(urllib2.Request(url, JSON.StringFromObject(request), headers)).read()
			response = JSON.ObjectFromString(body)
			if ('code' in response and response['code'] == 'InvalidCredentials'):
				Dict['auth_error'] = L('Invalid credentials')
				return False
			else:
				Dict['access_token'] = response['access_token']
				return True
		except urllib2.HTTPError, e:
			Dict['auth_error'] = L('Could not authenticate') + ': %s' % e.reason
			return e.code
		except:
			return L('ErrorNotRunning'), {}


####################################################################################################
def GetStill(item):
	if 'series' in item:
		if 'posters' in item['series']:
			for poster in item['series']['posters']:
				return 'https://oz-img.global.ssl.fastly.net' + poster + '?width=340'

	if 'posters' in item:
		for poster in item['posters']:
			return 'https://oz-img.global.ssl.fastly.net' + poster + '?width=340'

	if 'stills' in item:
		for still in item['stills']:
			return 'https://oz-img.global.ssl.fastly.net' + still + '?width=340'

	return None


####################################################################################################
def GetChannel(channels, channel):
	for ch in channels:
		if ch['key'] == channel:
			return ch
	return None


####################################################################################################
@handler(PREFIX, 'OZ', art=ART, thumb=ICON)
def MainMenu():
	
	oc = ObjectContainer()

	if Dict['auth_error'] != None:
		oc.title = L('Could not authenticate')
		oc.message = Dict['auth_error']
		return oc

	oc.add(DirectoryObject(key = Callback(NowMenu),                      title = L('Now')))
	oc.add(DirectoryObject(key = Callback(ChannelMenu),                  title = L('Channels')))
	oc.add(DirectoryObject(key = Callback(VodMenu, category = 'movies'), title = L('Movies')))
	oc.add(DirectoryObject(key = Callback(VodMenu, category = 'series'), title = L('TV Shows')))

	# Experimental
	oc.add(InputDirectoryObject(key = Callback(Search, title = L('Search')), prompt = L('Search'), title = L('Search')))

	return oc


####################################################################################################
@route(PREFIX + '/now')
def NowMenu(selected = None):

	oc = ObjectContainer(title2 = L('Now'))

	items = []
	channels = Request('indexes/user_channels')
	for channel in channels:
		items.append(channel['organization'] + ':' + channel['key'])

	schedule = Request('schedule/nowandnext?channels=' + ','.join(items))

	for item in schedule:
		if item[0] == None or 'content' not in item[0]:
			continue
		item = item[0]
		content = item['content']
		channel = GetChannel(channels, item['channel'])
		chkey = channel['organization'] + ':' + channel['key']
		obj = None
		title = channel['name'] + ': ' + content['title']
		thumb = GetStill(content)
		if thumb == None:
			thumb = 'http://image.l3.cdn.oz.com/still/'+item['channel']+'/tn?id=' + content['id']

		playStream = [
			MediaObject(
				parts = [PartObject(key=HTTPLiveStreamURL(Callback(PlayOffering, offering = channel['offerings'][0])))]
			)
		]

		if 'series' in content:
			obj = EpisodeObject(
				key = Callback(NowMenu, selected = content['id']),
				rating_key = content['id'],
				title = title,
				thumb = thumb,
				items = playStream
			)
		elif 'imdb_rating' in content:
			obj = MovieObject(
				key = Callback(NowMenu, selected = content['id']),
				rating_key = content['id'],
				title = title,
				thumb = thumb,
				items = playStream
			)
		else:
			obj = VideoClipObject(
				key = Callback(NowMenu, selected = content['id']),
				rating_key = content['id'],
				title = title,
				thumb = thumb,
				items = playStream
			)

		if obj != None and (selected == None or selected == content['id']):
			oc.add(obj)

	if len(oc) < 1:
		return NoContentFound(oc, title)

	return oc


####################################################################################################
@route(PREFIX + '/channels')
def ChannelMenu(selected = None):

	oc = ObjectContainer(title2 = L('Channels'))

	channels = Request('indexes/user_channels')

	for channel in channels:

		title = channel['name']
		thumb = channel['media']['icon']
		video = VideoClipObject(
			key = Callback(ChannelMenu, selected = channel['id']),
			rating_key = channel['id'],
			title = title,
			thumb = thumb,
			items = [
				MediaObject(
					parts = [PartObject(key=HTTPLiveStreamURL(Callback(PlayOffering, offering = channel['offerings'][0])))]
				)
			]
		)

		if (selected == None or selected == channel['id']):
			oc.add(video)

	if len(oc) < 1:
		return NoContentFound(oc, title)

	return oc


####################################################################################################
@route(PREFIX + '/vod')
def VodMenu(category = None):

	if category == 'series':
		title = L('TV Shows')

	if category == 'movies':
		title = L('Movies')

	oc = ObjectContainer(title2 = title)

	providers = Request('vod/providers')

	oc.add(DirectoryObject(key = Callback(VodMenuChannel, category = category, title = 'All'), title = L('All channels')))

	for provider in providers:
		if provider['has_access'] == True:
			oc.add(DirectoryObject(key = Callback(VodMenuChannel, category = category, title = provider['title'], provider = provider['id']), title = provider['title']))

	return oc

####################################################################################################
@route(PREFIX + '/vod/channel')
def VodMenuChannel(category, title, provider = False, page = 0, selected = None):

	title = transliterate(title)

	oc = ObjectContainer(title2 = title)

	url = 'vod?type=' + str(category) + '&items=50&page=' + str(page)

	if provider != '*':
		url = url + '&provider=' + str(provider)

	items = Request(url)

	for item in items:
		if 'series' in item:
			if 'title' in item['series']:
				title = item['series']['title']
			elif 'original_title' in item['series']:
				title = item['series']['original_title']
			else:
				title = L('Unknown')
			thumb = GetStill(item)
			if selected == None:
				oc.add(DirectoryObject(key = Callback(VodMenuSeries, title = title, series = item['series']['id']), title = title, thumb = thumb))
		else:
			content = item['content']
			offering = item['offerings'][0]
			title = GetTitle(content, offering)
			thumb = GetStill(content)
			if selected == None or selected == content['id']:
				oc.add(VideoClipObject(
					key = Callback(VodMenuChannel, category = category, title = title, provider = provider, page = page, selected = content['id']),
					rating_key = content['id'],
					title = title,
					thumb = thumb,
					items = [
						MediaObject(
							parts = [PartObject(key=HTTPLiveStreamURL(Callback(PlayOffering, offering = offering)))]
						)
					]
				))

	if len(oc) == 50:
		oc.add(NextPageObject(key = Callback(VodMenuChannel, category = category, title = title, provider = provider, page = int(page) + 1), title = L('More...')))

	if len(oc) < 1:
		return NoContentFound(oc, title)

	return oc


####################################################################################################
@route(PREFIX + '/vod/series')
def VodMenuSeries(title, series, selected = None):

	title = transliterate(title)

	oc = ObjectContainer(title2 = title)

	items = Request('vod/series/' + series + '/episodes')

	for item in items:
		content = item['content']
		offering = item['offerings'][0]
		title = GetTitle(content, offering)
		thumb = GetStill(content)
		if selected == None or selected == content['id']:
			oc.add(VideoClipObject(
				key = Callback(VodMenuSeries, title = title, series = series, selected = content['id']),
				rating_key = content['id'],
				title = title,
				thumb = thumb,
				items = [
					MediaObject(
						parts = [PartObject(key=HTTPLiveStreamURL(Callback(PlayOffering, offering = offering)))]
					)
				]
			))

	if len(oc) < 1:
		return NoContentFound(oc, title)

	return oc


####################################################################################################
@route(PREFIX + '/search')
def Search(query = ''):

	oc = ObjectContainer(title2 = L('Search results'))

	# get both movies and series
	url = 'vod?items=50&page=1&search=' + query
	items = Request(url)

	for item in items:
		if 'series' in item:
			if 'title' in item['series']:
				title = item['series']['title']
			elif 'original_title' in item['series']:
				title = item['series']['original_title']
			else:
				title = L('Unknown')
			thumb = GetStill(item)
			if selected == None:
				oc.add(DirectoryObject(key = Callback(VodMenuSeries, title = title, series = item['series']['id']), title = title, thumb = thumb))
		else:
			content = item['content']
			offering = item['offerings'][0]
			title = GetTitle(content, offering)
			thumb = GetStill(content)
			if selected == None or selected == content['id']:
				oc.add(VideoClipObject(
					key = Callback(VodMenuChannel, category = category, title = title, provider = provider, page = page, selected = content['id']),
					rating_key = content['id'],
					title = title,
					thumb = thumb,
					items = [
						MediaObject(
							parts = [PartObject(key=HTTPLiveStreamURL(Callback(PlayOffering, offering = offering)))]
						)
					]
				))

	if len(oc) == 50:
		oc.add(NextPageObject(key = Callback(VodMenuChannel, category = category, title = title, provider = provider, page = int(page) + 1), title = L('More...')))

	if len(oc) < 1:
		return NoContentFound(oc, title)

	return oc


####################################################################################################
def PlayOffering(offering):
	token = Request('offering/' + offering['organization'] + '/' + offering['key'] + '/token')
	return Redirect(token['url'])


####################################################################################################
def NoContentFound(oc, title):
	oc.header  = title
	oc.message = L('No content found')
	return oc


####################################################################################################
def GetTitle(content, offering = None):
	name = content['title']
	if 'season_number' in content:
		season_number = content['season_number']
		episode_number = content['episode_number']
		if season_number < 10:
			season_number = str('0') + str(season_number)
		if episode_number < 10:
			episode_number = str('0') + str(episode_number)
		name += ' - S' + str(season_number) + 'E' + str(episode_number)
	elif 'number_of_episodes' in content:
		name += ' - '
		name += str(content['episode_number']) + '/' + str(content['number_of_episodes'])
	elif 'year' in content:
		name += ' (' + str(content['year']) + ')'
	elif offering != None:
		created = Datetime.ParseDate(offering['create_time']).date()
		name += ' - '
		name += str(created.strftime('%d, %b %Y'))
	return name


####################################################################################################
def transliterate(s):
	s = s.replace('Á','A').replace('É','E').replace('Ð','D').replace('Ú','U').replace('Í','I').replace('Ó','O').replace('Ý','Y').replace('Þ','Th').replace('Æ','Ae').replace('Ö','O')
	s = s.replace('á','a').replace('é','e').replace('ð','d').replace('ú','u').replace('í','i').replace('ó','o').replace('ý','y').replace('þ','th').replace('æ','ae').replace('ö','o')
	return s
