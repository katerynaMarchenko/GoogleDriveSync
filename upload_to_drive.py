import datetime
import hashlib
import mimetypes
import time
import os
import httplib2

from apiclient import discovery
from oauth2client import client
from oauth2client import tools

from oauth2client.file import Storage
from apiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly',
          'https://www.googleapis.com/auth/drive.file',
          'https://www.googleapis.com/auth/drive']
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Drive Sync'

FULL_PATH = r'C:\\Users\\Matvey\\Desktop\\testFolder'
DIR_NAME = 'testFolder'
GOOGLE_MIME_TYPES = {
    'application/vnd.google-apps.document':
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.google-apps.spreadsheet':
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.google-apps.presentation':
    'application/vnd.openxmlformats-officedocument.presentationml.presentation'
}


def folder_upload(service):

    parents_id = {}

    for root, _, files in os.walk(FULL_PATH, topdown=True):
        last_dir = root.split('/')[-1]
        pre_last_dir = root.split('/')[-2]
        if pre_last_dir not in parents_id.keys():
            pre_last_dir = []
        else:
            pre_last_dir = parents_id[pre_last_dir]

        folder_metadata = {'name': last_dir,
                           'parents': [pre_last_dir],
                           'mimeType': 'application/vnd.google-apps.folder'}
        create_folder = service.files().create(body=folder_metadata,
                                               fields='id').execute()
        folder_id = create_folder.get('id', [])

        for name in files:
            file_metadata = {'name': name, 'parents': [folder_id]}
            media = MediaFileUpload(
                os.path.join(root, name),
                mimetype=mimetypes.MimeTypes().guess_type(name)[0])
            service.files().create(body=file_metadata,
                                   media_body=media,
                                   fields='id').execute()

        parents_id[last_dir] = folder_id

    return parents_id


def check_upload(service):
    results = service.files().list(
        pageSize=100,
        q="'root' in parents and trashed != True and \
        mimeType='application/vnd.google-apps.folder'").execute()

    items = results.get('files', [])

    if DIR_NAME in [item['name'] for item in items]:
        folder_id = [item['id']for item in items
                     if item['name'] == DIR_NAME][0]
    else:
        parents_id = folder_upload(service)
        folder_id = parents_id[DIR_NAME]

    return folder_id, FULL_PATH




def get_credentials():
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'drive-python-sync.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        credentials = tools.run_flow(flow, store, flags=None)
        print('Storing credentials to ', credential_path)
    return credentials


def get_tree(folder_name, tree_list, root, parents_id, service):
    folder_id = parents_id[folder_name]

    results = service.files().list(
        pageSize=1000,
        q=("%r in parents and \
        mimeType = 'application/vnd.google-apps.folder'and \
        trashed != True" % folder_id)).execute()

    items = results.get('files', [])
    root += folder_name + os.path.sep

    for item in items:
        parents_id[item['name']] = item['id']
        tree_list.append(root + item['name'])
        folder_id = [i['id'] for i in items
                     if i['name'] == item['name']][0]
        folder_name = item['name']
        get_tree(folder_name, tree_list,
                 root, parents_id, service)


def by_lines(input_str):
    return input_str.count(os.path.sep)


def main():
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('drive', 'v3', http=http)

    folder_id, full_path = check_upload(service)
    folder_name = full_path.split(os.path.sep)[-1]
    tree_list = []
    root = ''
    parents_id = {}

    parents_id[folder_name] = folder_id
    get_tree(folder_name, tree_list, root, parents_id, service)
    os_tree_list = []
    root_len = len(full_path.split(os.path.sep)[0:-2])

    for root, dirs, files in os.walk(full_path, topdown=True):
        for name in dirs:
            var_path = (os.path.sep).join(
                root.split(os.path.sep)[root_len + 1:])
            os_tree_list.append(os.path.join(var_path, name))

    remove_folders = list(set(tree_list).difference(set(os_tree_list)))
    upload_folders = list(set(os_tree_list).difference(set(tree_list)))
    exact_folders = list(set(os_tree_list).intersection(set(tree_list)))

    exact_folders.append(folder_name)
    upload_folders = sorted(upload_folders, key=by_lines)

    for folder_dir in upload_folders:
        var = os.path.join(full_path.split(os.path.sep)[0:-1]) + os.path.sep
        variable = var + folder_dir
        last_dir = folder_dir.split(os.path.sep)[-1]
        pre_last_dir = folder_dir.split(os.path.sep)[-2]

        files = [f for f in os.listdir(variable)
                 if os.path.isfile(os.path.join(variable, f))]

        folder_metadata = {'name': last_dir,
                           'parents': [parents_id[pre_last_dir]],
                           'mimeType': 'application/vnd.google-apps.folder'}
        create_folder = service.files().create(
            body=folder_metadata, fields='id').execute()
        folder_id = create_folder.get('id', [])
        parents_id[last_dir] = folder_id

        for os_file in files:
            some_metadata = {'name': os_file, 'parents': [folder_id]}
            os_file_mimetype = mimetypes.MimeTypes().guess_type(
                os.path.join(variable, os_file))[0]
            media = MediaFileUpload(os.path.join(variable, os_file),
                                    mimetype=os_file_mimetype)
            upload_this = service.files().create(body=some_metadata,
                                                 media_body=media,
                                                 fields='id').execute()
            upload_this = upload_this.get('id', [])

    for folder_dir in exact_folders:

        var = (os.path.sep).join(full_path.split(
            os.path.sep)[0:-1]) + os.path.sep

        variable = var + folder_dir
        last_dir = folder_dir.split(os.path.sep)[-1]
        os_files = [f for f in os.listdir(variable)
                    if os.path.isfile(os.path.join(variable, f))]
        results = service.files().list(
            pageSize=1000, q=('%r in parents and \
            mimeType!="application/vnd.google-apps.folder" and \
            trashed != True' % parents_id[last_dir]),
            fields="files(id, name, mimeType, \
            modifiedTime, md5Checksum)").execute()

        items = results.get('files', [])

        refresh_files = [f for f in items if f['name'] in os_files]
        remove_files = [f for f in items if f['name'] not in os_files]
        upload_files = [f for f in os_files
                        if f not in [j['name']for j in items]]

        for drive_file in refresh_files:
            file_dir = os.path.join(variable, drive_file['name'])
            file_time = os.path.getmtime(file_dir)
            mtime = [f['modifiedTime']
                     for f in items if f['name'] == drive_file['name']][0]
            mtime = datetime.datetime.strptime(
                mtime[:-2], "%Y-%m-%dT%H:%M:%S.%f")
            drive_time = time.mktime(mtime.timetuple())
            os_file_md5 = hashlib.md5(open(file_dir, 'rb').read()).hexdigest()
            if 'md5Checksum' in drive_file.keys():
                drive_md5 = drive_file['md5Checksum']
            else:
                drive_md5 = None

            if (file_time > drive_time) or (drive_md5 != os_file_md5):
                file_id = [f['id'] for f in items
                           if f['name'] == drive_file['name']][0]
                file_mime = [f['mimeType'] for f in items
                             if f['name'] == drive_file['name']][0]

                file_metadata = {'name': drive_file['name'],
                                 'parents': [parents_id[last_dir]]}
                media_body = MediaFileUpload(file_dir, mimetype=file_mime)
                service.files().update(fileId=file_id,
                                       media_body=media_body,
                                       fields='id').execute()

        for drive_file in remove_files:

            file_id = [f['id'] for f in items
                       if f['name'] == drive_file['name']][0]
            service.files().delete(fileId=file_id).execute()

        for os_file in upload_files:

            file_dir = os.path.join(variable, os_file)

            filemime = mimetypes.MimeTypes().guess_type(file_dir)[0]
            file_metadata = {'name': os_file,
                             'parents': [parents_id[last_dir]]}
            media_body = MediaFileUpload(file_dir, mimetype=filemime)

            service.files().create(body=file_metadata,
                                   media_body=media_body,
                                   fields='id').execute()

    remove_folders = sorted(remove_folders, key=by_lines, reverse=True)

    for folder_dir in remove_folders:
        var = (os.path.sep).join(full_path.split(
            os.path.sep)[0:-1]) + os.path.sep
        variable = var + folder_dir
        last_dir = folder_dir.split('/')[-1]
        folder_id = parents_id[last_dir]
        service.files().delete(fileId=folder_id).execute()

if __name__ == '__main__':
    main()
