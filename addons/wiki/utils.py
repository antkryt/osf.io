import os
from urllib.parse import quote
import uuid

from pymongo import MongoClient
import requests

from addons.wiki import settings as wiki_settings
# MongoDB forbids field names that begin with "$" or contain ".". These
# utilities map to and from Mongo field names.

mongo_map = {
    '.': '__!dot!__',
    '$': '__!dollar!__',
}

def to_mongo(item):
    for key, value in mongo_map.items():
        item = item.replace(key, value)
    return item

def to_mongo_key(item):
    return to_mongo(item).strip().lower()


def get_sharejs_uuid(node, wname):
    """
    Format private uuid into the form used in mongo and sharejs.
    This includes node's primary ID to prevent fork namespace collision
    """
    wiki_key = to_mongo_key(wname)
    private_uuid = node.wiki_private_uuids.get(wiki_key)
    return str(uuid.uuid5(
        uuid.UUID(private_uuid),
        str(node._id)
    )) if private_uuid else None


def share_db():
    """Generate db client for sharejs db"""
    client = MongoClient(wiki_settings.SHAREJS_DB_URL, tlsAllowInvalidCertificates=True)
    return client[wiki_settings.SHAREJS_DB_NAME]


def broadcast_to_sharejs(action, sharejs_uuid, node=None, wiki_name='home', data=None):
    """
    Broadcast an action to all documents connected to a wiki.
    Actions include 'lock', 'unlock', 'redirect', and 'delete'
    'redirect' and 'delete' both require a node to be specified
    'unlock' requires data to be a list of contributors with write permission
    """

    url = 'http://{host}:{port}/{action}/{id}/'.format(
        host=wiki_settings.SHAREJS_HOST,
        port=wiki_settings.SHAREJS_PORT,
        action=action,
        id=sharejs_uuid
    )

    if action == 'redirect' or action == 'delete':
        redirect_url = quote(
            node.web_url_for('project_wiki_view', wname=wiki_name, _guid=True),
            safe='',
        )
        url = os.path.join(url, redirect_url)

    try:
        requests.post(url, json=data)
    except requests.ConnectionError:
        pass    # Assume sharejs is not online


def serialize_wiki_widget(node):
    from addons.wiki.models import WikiVersion

    wiki = node.get_addon('wiki')
    wiki_version = WikiVersion.objects.get_for_node(node, 'home')

    # Show "Read more" link if there are multiple pages or has > 400 characters
    more = node.wikis.filter(deleted__isnull=True).count() >= 2
    MAX_DISPLAY_LENGTH = 400
    rendered_before_update = False
    if wiki_version and wiki_version.content:
        if len(wiki_version.content) > MAX_DISPLAY_LENGTH:
            more = True
        rendered_before_update = wiki_version.rendered_before_update

    # Content fetched and rendered by front-end
    wiki_html = None

    wiki_widget_data = {
        'complete': True,
        'wiki_content': wiki_html if wiki_html else None,
        'wiki_content_url': node.api_url_for('wiki_page_content', wname='home'),
        'rendered_before_update': rendered_before_update,
        'more': more,
        'include': False,
    }
    wiki_widget_data.update(wiki.config.to_json())
    return wiki_widget_data
