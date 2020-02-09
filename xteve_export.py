import json
import argparse
import os, sys, importlib
import requests

from xml.etree import ElementTree

sys.path.append('./m3u-epg-editor/')
m3u_epg_editor = importlib.import_module("m3u-epg-editor-py3")


MODES = {
    "XMLTV": "xmltv",
    "M3U": "m3u"
}
TMP_FOLDER = "tmp"

arg_parser = argparse.ArgumentParser(
    description='read xTeve config and return request export')
arg_parser.add_argument(
    'export_type', default=MODES['M3U'], help='Type of export', nargs='?', choices=MODES.values())
arg_parser.add_argument('--debug', '-d', action='store_true',
                        help='Enable Debugging')
args = vars(arg_parser.parse_args())


def _getNS(opts):
    nsOps = argparse.Namespace()
    for key in opts.keys():
        setattr(nsOps, key, opts[key])
    return nsOps

def _createM3U(settings):

    m3u_files = settings['files']['m3u']
    filtered_m3u_entries = []
    for m3u_entry in m3u_files.values():
        opts = {
            "m3uurl": m3u_entry["file.source"],
            "outdirectory": TMP_FOLDER,
            "no_tvg_id": True
        }

        m3u_entries = m3u_epg_editor.load_m3u(_getNS(opts))

        filters = settings['filter']

        if m3u_entries is not None and len(m3u_entries) > 0:
            for key in filters:
                filter = filters[key]
                if(filter['active'] and filter['type'] == 'group-title'):
                    group_filter = filter['filter']
                    channel_include = list(
                        map(str.strip, filter['include'].split(",")))
                    channel_exclude = list(
                        map(str.strip, filter['exclude'].split(",")))
                    # remove empty string from exclusion list 
                    channel_exclude = [x for x in channel_exclude if x]
                    for m3u_entry in m3u_entries:
                        group_included = m3u_epg_editor.is_item_matched(
                            [group_filter], m3u_entry.group_title)
                        channel_included = m3u_epg_editor.is_item_matched(
                            channel_include, m3u_entry.tvg_name)
                        channel_excluded = m3u_epg_editor.is_item_matched(
                            channel_exclude, m3u_entry.tvg_name)
                        if (group_included and channel_included and not channel_excluded):
                            filtered_m3u_entries.append(m3u_entry)
    return filtered_m3u_entries

if not args['debug']:
    def _output_str_dummy(event_str):
        return
    m3u_epg_editor.output_str = _output_str_dummy


with open('/srv/home/christian/.xteve/settings.json') as settings_file:
    settings = json.load(settings_file)
    if(args['export_type'] == MODES['M3U']):
        filtered_m3u_entries = _createM3U(settings)
        
        if filtered_m3u_entries is not None and len(filtered_m3u_entries) > 0:
            opts = {
                "outfilename": "output",
                "outdirectory": TMP_FOLDER,
                "preserve_case": True,
                "tvh_start": 0,
                "tvh_offset": 0,
                "http_for_images": False
            }
            m3u_epg_editor.save_new_m3u(_getNS(opts), filtered_m3u_entries)
            m3u_file = os.path.join(
                opts['outdirectory'], opts['outfilename'] + ".m3u8")
            with open(m3u_file, 'r') as fin:
                print(fin.read())

    if(args['export_type'] == MODES['XMLTV']):

        m3u_entries = _createM3U(settings)
        epg_files = settings['files']['xmltv']
        filtered_epg_entries = []
        for epg_entry in epg_files.values():
            opts = {
                "epgurl": epg_entry["file.source"],
                "outdirectory": TMP_FOLDER,
                "http_for_images": False,
                "preserve_case": True,
                "force_epg": False,
                "no_tvg_id": True,
                "xml_sort_type": None,
                "range": 168
            }
            epg_filename = m3u_epg_editor.load_epg(_getNS(opts))
            epg_filename = "tmp/original.xml"

            if epg_filename is not None:
                xml_tree = m3u_epg_editor.create_new_epg(
                    _getNS(opts), epg_filename, m3u_entries)
                if xml_tree is not None:
                    ElementTree.dump(xml_tree)

    if not args['debug']:
        for filename in os.listdir(TMP_FOLDER):
            file_path = os.path.join(TMP_FOLDER, filename)
            try:
                os.unlink(file_path)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (file_path, e))
