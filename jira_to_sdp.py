import mimetypes
import requests
from io import BytesIO
import json
import psycopg2_com as db
from requests.auth import HTTPBasicAuth
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import re, os

#comm

def get_filename(body):
    match = re.search(r'(?:\[\^|!)([^|\]\(]+)', body)
    if match:
        full_name = match.group(1).strip()            # ex: Screenshot 2024-07-18 174820.png
        ext = os.path.splitext(full_name)[1].lstrip('.')
        # print(full_name, ext)
        return full_name, ext
    return "", ""  

def has_attachments(body):
    # for block in body.get("content", []):
    #     if block.get("type") == "paragraph":
    #         for inner in block.get("content", {}):
    #             # print(inner)
    #             # print(block.get("content", []))
    #             if "media" in inner.get("type"):
    #                 return True
    for block in body.get('content', []):
        if block.get('type') == 'mediaSingle' or 'mediaInline':
            return True
    return False

def search_att(filename,jira_url, jira_key, jira_auth):
    att_url = f'{jira_url}/rest/api/3/issue/{jira_key}?fields=attachment'
    response = requests.get(att_url, auth=jira_auth)
    response_att =response.json()
    for att in response_att['fields']['attachment']:
        if att['filename'] == filename:
            return att['content']
    return None

def add_comm(description, headers_sdp, url_sdp, ticket_id):
    url_post= f'{url_sdp}/api/v3/requests/{ticket_id}/notes'
    input_data = f'''{{
    "note": {{
        "description": "{description}",
        "show_to_requester": true,
        "mark_first_response": false,
        "add_to_linked_requests": true
    }}
    }}'''

    data = {'input_data': input_data}
    response = requests.post(url_post,headers=headers_sdp,data=data,verify=False)
    return response.json()['note']['id']

def add_att(filename, ext, url_sdp, headers,jira_att_url, jira_auth, id_sdp, id_com):

    upload_url = f"{url_sdp}/api/v3/requests/{id_sdp}/notes/{id_com}/upload"

    # Descărcare în memorie
    response = requests.get(jira_att_url, auth=jira_auth)
    response.raise_for_status()
    # print(response.json())
    # Conținutul fișierului e acum în variabilă
    file_data = BytesIO(response.content)


    file_name = f"{filename}"  # Pune ce vrei aici
    file_type = "application/pdf" if ext == 'pdf' else 'image/png' # Sau "application/pdf", etc. în funcție de extensie

        # === 2. Upload to SDPlus ===
    files = {
            'input_file': (file_name, file_data, file_type)
        }
    response = requests.put(upload_url,headers=headers,files=files,verify=False)

def copy_comment_to_sdplus(ticket_id, comm_jira_id, url_sdp, headers_sdp, url_jira,jira_key, jira_auth):
    # ticket_id = sq.get_ticket_id(response['issue']['id'])
    api_link = f'{url_sdp}/api/v3/requests/{ticket_id}/notes'

    #verific daca am atasamente la comentariu in jira
    get_com_url = f'{url_jira}/rest/api/3/issue/{jira_key}/comment/{comm_jira_id}/'
    response_jira = requests.get(get_com_url, auth=jira_auth)

    #creez comentariul in sdplus
    text = response_jira.json()['body']["content"][0]["content"][0]["text"]
    comm_id = add_comm(text, headers_sdp,url_sdp, ticket_id)
    response_com = response_jira.json()
    # print(response_com)
    if has_attachments(response_com['body']):
        # print('aaaa: ',db.get_webhook_body(str(comm_jira_id)))
        filename, ext = get_filename(db.get_webhook_body(str(comm_jira_id)))
        if search_att(filename,url_jira,jira_key,jira_auth):
            download_link = search_att(filename,url_jira,jira_key,jira_auth)
            # print(download_link)
            add_att(filename, ext, url_sdp, headers_sdp,download_link, jira_auth, ticket_id, comm_id)



#tickete
def extract_description_text(issue_data):
    desc = issue_data.get("fields", {}).get("description", {})
    text_parts = []

    for block in desc.get("content", []):
        for item in block.get("content", []):
            if item.get("type") == "text":
                text_parts.append(item.get("text", ""))

    return " ".join(text_parts)

def set_priority(priority):
    copy = priority
    match copy.lower():   # transformă în lowercase ca să fie sigur
        case 'lowest':
            return "Low"
        case 'low':
            return 'Normal'
        case "highest":
            return "High"
        case _:
            return priority
        
def set_status(status):
    copy = status
    match copy.lower():   # transformă în lowercase ca să fie sigur
        case 'to do':
            return "Open"
        case 'waiting for customer':
            return 'Onhold'
        case _:
            return status
        
def create_sd_ticket(jira_key, jira_url, jira_auth, url_sdp, headers_sdp):
    post_url = f'{url_sdp}/api/v3/requests'

    get_issue_url = f'{jira_url}/rest/api/3/issue/{jira_key}'
    response_jira = requests.get(get_issue_url, auth =jira_auth)
    input_data = json.dumps({
        "request": {
            "subject": response_jira.json()["fields"]["summary"],
            "description": extract_description_text(response_jira.json()),
            "priority": {
                'name': set_priority(response_jira.json()['fields']['priority']['name'])
            },
            "requester": {
                "name": "administrator"  # Sau ID dacă știi exact
            },
            'status':{
                'name': set_status(response_jira.json()['fields']['status']['name'])
            }
        }
    })
    
    payload = {"input_data": input_data}
    response_sd = requests.post(post_url, data=payload, headers=headers_sdp, verify=False)
    db.insert_id_ticket_sync(response_sd.json()['request']['id'], jira_key)

    attachments = response_jira.json()['fields'].get("attachment", [])

    if attachments:
        ticket_id = response_sd.json()['request']['id']
        upload_url_sdp = f'{url_sdp}/api/v3/requests/{ticket_id}/upload'

        for attachment in attachments:
            file_url = attachment['content']  # URL pentru download fișier
            file_name = attachment['filename']
            file_type = attachment['mimeType']
            
            # Descarcă fișierul din Jira
            file_response = requests.get(file_url, auth=jira_auth)

            if file_response.status_code == 200:
                file_data = BytesIO(file_response.content)
                print(file_name, file_data, file_type)
                files = {
                    'input_file': (file_name, file_data, file_type)
                }

                upload_response = requests.put(upload_url_sdp, headers=headers_sdp, files=files, verify=False)
                # print("Răspuns SDPlus:", upload_response.status_code)
                # print("Body:", upload_response.text)

                # if upload_response.status_code == 200:
                #     print(f"✅ Fișier '{file_name}' încărcat cu succes.")
                # else:
                #     print(f"⛔ Eroare la încărcarea fișierului '{file_name}': {upload_response.status_code}")
            else:
                print(f"⛔ Eroare la descărcarea fișierului din Jira: {file_response.status_code}")


#status 
def update_status(sdp_id, sdp_url, sdp_headers, status):
    url = f'{sdp_url}/api/v3/requests/{sdp_id}'
    input_data = {
        "request": {
            "status": {"name": sd_status} 
        }
    }
    payload = {"input_data": json.dumps(input_data)}

    resp = requests.put(url, headers=sdp_headers, data=payload, verify=False)
    # print(resp.json())


#main code
with open("config.json") as f:
    config = json.load(f)
JIRA_URL = config["jira"]["url"]
JIRA_TOKEN = config["jira"]["token"]
JIRA_EMAIL = config["jira"]["mail"]
JIRA_AUTH = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
SDP_URL = config["sdplus"]["url"]
SDP_TOKEN = config["sdplus"]["token"]
headers_sdp = {"authtoken": "5CF839EE-0BC3-4EC2-B752-8037F8F42B02", "PORTALID":"1"}

# db.drop_sync_tables()
# print(db.get_counter())
# print('issues: ', db.get_ticket_sync(0))
# print('Comments: ', db.get_comment_sync(0))
# print('issues status: ', db.get_status_sync(0))

cnt1, cnt2, cnt3 = 0, 0, 0 
# cnt1, cnt2, cnt3 = int(db.get_counter()[0][1]), int(db.get_counter()[0][2]), int(db.get_counter()[0][3])
# print(cnt1, cnt2, cnt3)

# for row in db.get_ticket_sync(cnt1):
#     cnt1, key, _ = row
#     create_sd_ticket(key, JIRA_URL, JIRA_AUTH, SDP_URL, headers_sdp)

# for row in db.get_comment_sync(cnt2):
#     cnt2, key, comm_id, _ = row
#     sdp_id = db.get_sdp_id(key)
#     copy_comment_to_sdplus(sdp_id, comm_id, SDP_URL, headers_sdp, JIRA_URL, key, JIRA_AUTH)

# for row in db.get_status_sync(cnt3):
#     cnt3, key, status = row
#     sd_status = set_status(status)
#     ticket_id = db.get_sdp_id(key)
#     update_status(ticket_id, SDP_URL, headers_sdp, sd_status)

db.counter_db(cnt1, cnt2, cnt3)
