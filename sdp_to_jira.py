from requests.auth import HTTPBasicAuth
import requests, json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from bs4 import BeautifulSoup
import psycopg2_com as db


#issue
def get_ticket(ticket_id, sdp_url, headers_sdp):
    url = f'{sdp_url}/api/v3/requests/{ticket_id}'
    response = requests.get(url,headers=headers_sdp,verify=False)
    return response.json()

def set_priority_issue(priority):
    copy = priority
    match copy.lower():   # transformă în lowercase ca să fie sigur
        case "normal":
            return "Low"
        case "low" |'not specified':
            return "Lowest"
        case _:
            return priority

#status
def set_status_issue(status):
    copy = status
    match copy.lower():   # transformă în lowercase ca să fie sigur
        case "open":
            return "To Do"
        case "onhold" :
            return "Waiting for customer"
        case _:
            return status
        
def transition_issue(jira_url, issue_key, auth, target_name):
    url = f"{jira_url}/rest/api/3/issue/{issue_key}/transitions"
    #scot tranzitiile posibile

    data = requests.get(url,headers={"Accept": "application/json"},auth=auth)
    transitions = data.json()["transitions"]
    # găsește ID-ul tranziției după numele afișat
    t = next((t for t in transitions if t["name"].lower() == target_name.lower()), None)
    if not t:
        raise ValueError(f"Tranziția '{target_name}' nu există. Disponibile: {[x['name'] for x in transitions]}")
    payload = {"transition": {"id": t["id"]}}
    r = requests.post(url, json=payload,
                      headers={"Accept":"application/json","Content-Type":"application/json"},
                      auth=auth)
    # Succes tipic: 204 No Content
    if r.status_code not in (204, 200):
        raise RuntimeError(f"Eșec tranziție: {r.status_code} {r.text}")
    
#issue
def upload_att(jira_url, issueId, jira_auth, content, filename, app_type):
    url = f'{jira_url}/{issueId}/attachments'
    headers = {
        "Accept": "application/json",
        "X-Atlassian-Token": "no-check"
    }
    response = requests.request("POST",url,headers = headers,auth = jira_auth,files = {"file": (filename, content, app_type)})
    return response.json()


def create_issue(ticket, url, jira_auth,  project_key, headers_sdp, sdp_url):
    jira_priority = set_priority_issue(ticket['request']['priority']['name'])
    jira_status = set_status_issue(ticket['request']['status']['name'])
    print(jira_priority, jira_status)
    description_html = ticket['request'].get("description", "")

    # 2. Curăță HTML-ul → text simplu
    soup = BeautifulSoup(description_html, "html.parser")
    description_text = soup.get_text(separator="\n").strip()

    jira_url = f'{url}/rest/api/3/issue'
    headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
    }

     # blocuri ADF
    content_blocks = []
    content_blocks.append({
        "type": "paragraph",
        "content": [
            {
                "type": "text",
                "text": f'{description_text}'
            }
        ]
    })

    ticket_data_jira = json.dumps({
        "fields": {
            "project": {
                "key": project_key #configurabil
            },
            "summary": ticket['request']["subject"],
            "description": {
                "type": "doc",
                "version": 1,
                "content": content_blocks
            },
            "issuetype": {"name": "Task"},
            "priority":{'name': jira_priority},
            # 'statusCategory':{'name': jira_status}
        }
    })

    response_jira_post = requests.post(jira_url, data=ticket_data_jira,headers=headers, auth=jira_auth)
    response_jira = response_jira_post.json()
    db.insert_key_issue_sync(response_jira['key'], ticket['request']['id'])
    # print(response_jira)
    
    #adaug atasementele la descrierea issue-ului
    if ticket['request']["attachments"]:
        content_blocks.append({
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": 'Atasamente:'
                    }
                ]
            })
        for att in ticket['request']["attachments"]:
            response = requests.get(f'{sdp_url}/{att["content_url"]}',headers=headers_sdp,verify=False)
            upload_att(jira_url, response_jira['key'],jira_auth, response.content, att['name'] ,att["content_type"])
            content_blocks.append({
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": att['name']
                    }
                ]
            })

            payload = {
                'fields':{
                    'description':{
                        "type": "doc",
                        "version": 1,
                        "content": content_blocks
                    }   
                }
                
            }
            url_2 = f"{jira_url}/{response_jira['key']}"
            response_post_2 = requests.put(url_2, data=json.dumps(payload), headers=headers, auth=jira_auth)
            # print("Status:", response_post_2.status_code)
            # print(response_post_2.json())
            # print("Text:", response_post_2.text)
    
    transition_issue(url,response_jira['key'],jira_auth, jira_status)
    
#comm
def get_note_details(request_id, note_id, headers, sd_url):
    url = f"{sd_url}/api/v3/requests/{request_id}/notes/{note_id}"
    response = requests.get(url,headers=headers,verify=False)
    return response.json()

def add_comment(url_p, id, auth, description, names):
    url = f"{url_p}/rest/api/3/issue/{id}/comment"

    headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
    }

    # blocuri ADF
    content_blocks = []

    # text normal
    if description:
        content_blocks.append({
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": f'{description}'
                }
            ]
        })

    # atașamente inline
    if names: 
        content_blocks.append({
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": 'Atasamente:'
                    }
                ]
            })
        for att_name in names:
            content_blocks.append({
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": att_name
                    }
                ]
            })
        payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": content_blocks
        }
        }
        response = requests.post(url, data=json.dumps(payload), headers=headers, auth=auth)
        return response.json()['id']

def download_att(headers, link):
    response = requests.get(link,headers=headers,verify=False)
    return response

def upload_att_com(url, id, auth, att, filename):
    jira_url = f"{url}/rest/api/3/issue/{id}/attachments"

    headers = {
        "Accept": "application/json",
        "X-Atlassian-Token": "no-check"
    }

    files = {"file": (filename, att.content, "application/octet-stream")}
    jira_resp = requests.post(jira_url, headers=headers, auth=auth, files=files)
    data = jira_resp.json()
    # vezi ce primești efectiv
    # print("Upload response:", data)
      # returnează doar lista de id-uri
    return [item["filename"] for item in data]

def copy_note_to_jira(comment, jira_issue_id, jira_auth, jira_url, headers_sd):
    # 1. Extrage HTML-ul
    description_html = comment['note'].get("description", "")

    # 2. Curăță HTML-ul → text simplu
    soup = BeautifulSoup(description_html, "html.parser")
    description_text = soup.get_text(separator="\n").strip()
    # print(comment["note"]["id"])

    # 3. Verifică atașamentele
    attachments = comment['note'].get("attachments", [])
    att_ids = []
    if attachments:
        for att in attachments:
            file_name = att["name"]
            download_link = att.get("content_url", "")
            full_link = f"https://localhost:8080{download_link}"  # ajustează cu url-ul corect
            # print(full_link)
            content = download_att(headers_sd, full_link)
            uploaded_ids = upload_att_com("https://practica.atlassian.net",  jira_issue_id, jira_auth, content, file_name)
            att_ids.extend(uploaded_ids)
    return add_comment("https://practica.atlassian.net",jira_issue_id,jira_auth,description_text,att_ids)

#main code
with open("config.json") as f:
    config = json.load(f)
JIRA_URL = config["jira"]["url"]
JIRA_TOKEN = config["jira"]["token"]
JIRA_EMAIL = config["jira"]["mail"]
JIRA_AUTH = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
JIRA_PROJECT_KEY = config["jira"]["project_key"]
SDP_URL = config["sdplus"]["url"]
SDP_TOKEN = config["sdplus"]["token"]
headers_sdp = {"authtoken": "5CF839EE-0BC3-4EC2-B752-8037F8F42B02", "PORTALID":"1"}

# db.drop_sync_tables() 

cnt4, cnt5, cnt6 = int(db.get_counter_sdp()[0][1]), int(db.get_counter_sdp()[0][2]), int(db.get_counter_sdp()[0][3])
print(cnt4, cnt5, cnt6)
# cnt4, cnt5, cnt6 = 0, 0, 0

# for row in db.get_issue_sync(cnt4):
#     cnt4, _, ticket_id = row
#     ticket = get_ticket(ticket_id, SDP_URL, headers_sdp)
#     create_issue(ticket, JIRA_URL, JIRA_AUTH, JIRA_PROJECT_KEY, headers_sdp, SDP_URL)

for row in db.get_note_sync(cnt5):
    cnt5, ticket_id, note_id= row
    jira_key = db.get_issue_key(ticket_id)
    comment = get_note_details(ticket_id,note_id, headers_sdp, SDP_URL)
    copy_note_to_jira(comment, jira_key, JIRA_AUTH, JIRA_URL, headers_sdp)

for row in db.get_status_sync(cnt6):
    cnt6, sdp_id, status = row
    jira_key = db.get_issue_key(sdp_id)
    jira_status = set_status_issue(status)
    transition_issue(JIRA_URL,jira_key,JIRA_AUTH,jira_status)

db.counter_sdp(cnt4, cnt5, cnt6)


# print(get_ticket(72, SDP_URL, headers_sdp))
# get_issue_url = f'{JIRA_URL}/rest/api/3/issue/KAN-77'
# response_jira = requests.get(get_issue_url, auth =JIRA_AUTH)
# print(response_jira.json())

# ticket = get_ticket(72, SDP_URL,headers_sdp)
# create_issue(ticket,JIRA_URL, JIRA_AUTH, JIRA_PROJECT_KEY,headers_sdp, SDP_URL)

# headers = {
#         "Accept": "application/json",
#         "X-Atlassian-Token": "no-check"
#     }
# response_t = requests.get("https://practica.atlassian.net/rest/api/3/issue/KAN-75?fields=attachment", headers= headers, auth=JIRA_AUTH)
# print(response_t.json())

# r = requests.get("https://practica.atlassian.net/rest/api/3/attachment/10314", headers=headers, auth=JIRA_AUTH)
# media_url = r.url  # URL final după redirect
# print(r.json())
# extrage UUID din path, dacă e acolo
# url_test = 'https://localhost:8080/api/v3/requests/72/notes/713'
# comment = requests.get(url_test,headers=headers_sdp,verify=False)
# comment = comment.json()
# copy_note_to_jira(comment, 'KAN-114', JIRA_AUTH, JIRA_URL, headers_sdp)

# transition_issue(JIRA_URL,'KAN-117',JIRA_AUTH, 'In Progress')