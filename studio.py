

import sys
import tempfile
import streamlit as st
from openai import OpenAI
from docx import Document
import requests
from PIL import Image
from io import BytesIO
import fitz
import json
import http.client
import pprint
import time 
from io import StringIO
from docx import Document
import PyPDF2
import os
import io
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request
load_dotenv()



client = OpenAI(
  api_key= os.getenv("OPENAI_KEY")
)


st.set_page_config(page_title="📄 Document Reader", layout="centered")

st.title(":blue[Studio Stream]")

st.title("Enter a project name")
with st.form("project_form"):
    project_name = st.text_input("Enter Project Name")
    submitted = st.form_submit_button("Create Project")

    if submitted:
        if project_name.strip():
            st.success(f"Project '{project_name}' created successfully!")
        else:
            st.error("Please enter a valid project name.")


content =""
st.title("Upload & Process")

mode = st.radio("Select input type:", ["Audio", "Document", "Text"])

if mode == "Audio":
    uploaded = st.file_uploader("Upload an audio file", type=["m4a", "mp3", "wav"])
    if uploaded is not None:
        audio_bytes = uploaded.read()
        # file-like for API
        audio_file = io.BytesIO(audio_bytes)

        # if your API needs a filesystem path
        suffix = f".{uploaded.name.split('.')[-1]}"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(audio_bytes)
        tmp.flush()
        audio_file = open(tmp.name, "rb")

        resp = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=audio_file
        )
        content = resp.text

    else:
        st.info("Please upload an audio file to transcribe.")


elif mode == "Document":
    uploaded = st.file_uploader("Upload a document", type=["pdf", "docx", "txt"])
    if uploaded is not None:
        file_ext = uploaded.name.rsplit(".", 1)[-1].lower()

        def read_pdf(f):
            reader = PdfReader(f)
            return "".join(page.extract_text() or "" for page in reader.pages)

        def read_docx(f):
            doc = Document(f)
            return "\n".join(p.text for p in doc.paragraphs)

        def read_txt(f):
            return StringIO(f.getvalue().decode("utf-8")).read()

        if file_ext == "pdf":
            content = read_pdf(uploaded)
        elif file_ext == "docx":
            content = read_docx(uploaded)
        elif file_ext == "txt":
            content = read_txt(uploaded)
        else:
            st.error("Unsupported file type.")
            content = ""

    else:
        st.info("Please upload a document file.")


else:  # Text mode
    content = st.text_area("Paste or type your text here")
    if not content:
        st.info("Enter some text above to continue.")


# ——— Show the result ———
#if 'content' in locals() and content:
    #st.subheader("Processed Content")
    #st.write(content)
    # st.subheader("📜 Document Content")
    # st.text_area("Text from document:", content, height=400)



if content:
    completion = client.chat.completions.create(
        model="gpt-4o-mini",  # or "gpt-4o-mini" if available
        store=True,
        messages=[
            {
                "role": "system",
                "content": """
    You are a professional product and design brief assistant. Given a creative prompt or description of a t-shirt design project, extract the following details in a structured and detailed format.

    Return your output in this format:
    ---
    Overview:
    [brief description of the project purpose, background, intended use]

    Target Audience:
    - Age group:
    - Interests/Lifestyle:
    - Visual appeal (style preferences):
    - Cultural/Regional considerations:

    Design Goals:
    - Intended emotion/message:
    - Overall tone (high-energy, modern, minimal, etc.):
    - Suggested visual style (streetwear, retro, abstract, etc.):

    Key Design Elements:
    1. Subject:
    2. Action:
    3. Environment:
    4. Color scheme:

    What should NOT be used:
    - Unwanted colors:
    - Design techniques to avoid (gradients, photorealism, etc.):
    - Unnecessary complexities:
    - Culturally inappropriate/distracting elements:

    Referecnce Links:
    - Ref 1: 
    - Ref 2: 
    - Ref 3:
    - Ref 4: 
    - Ref 5:

    Constraints:
    - 6 colours maximum
    - Vector image traceable
    - Screen print ready
    - 4:5 ratio
    - No gradients
    - No 3D textures
    - Only low detail shading and highlights
    - Floating objects 
    - no frames
    - no backgrounds
    - .5mm line widths at a minimum
    - Low complexity
    - Minimalist artwork
    - Solid colours, no tints
    - --ar 4:5 --stylize 120-160 --quality 2
    ---
    Be specific and extarct information as it is, without adding additional content on your own.
    """
            },
            {
                "role": "user",
                "content":content
            }
        ]
    )


    with st.spinner('Extarcting Data...'):
        extarct_response = completion.choices[0].message.content
        st.subheader("📜 Extarcted Content")
        st.text_area("Text from document:",extarct_response, height=400)


    ##Converting into a dictionary
    def parse_gpt_output(gpt_text):
        """
        Parses GPT output into a dictionary, where each heading (ending with ':')
        becomes a key, and the lines that follow (until the next heading) become
        a list of strings.
        """
        sections = {}
        current_key = None

        for line in gpt_text.splitlines():
            line = line.strip()
            
            # Skip blank lines
            if not line:
                continue
            
            # If the line ends with a colon, treat it as a heading
            if line.endswith(':'):
                # Remove the colon to create the dictionary key
                current_key = line[:-1].strip()
                sections[current_key] = []
            else:
                # Otherwise, treat it as content for the current heading
                if current_key is not None:
                    sections[current_key].append(line)
                else:
                    # If no heading has been found yet, skip or handle as needed
                    pass

        return sections



    parsed_dict = parse_gpt_output(extarct_response)



    ##Research and Analysis: 
    def generate_structured_design_insights(project_data, client):
        """
        Extracts the "Overview" and "Reference Links" from project_data,
        sends them to GPT with instructions to return a structured JSON response.
        In the JSON:
        - Each design theme is given as a key and its value is a dictionary combining:
            • Design Concept
            • Artistic Approach
            • (Optionally) a list of style techniques related to that theme.
        - Additional sections like Color Palettes, Suggestions for Kids’ Designs,
            and a Conclusion are also included.
        
        :param project_data: dict containing project details with at least
                            "Overview", "Reference Links", "Key Design Elements" and "Target Audience" keys.
        :param client: The client object to call the GPT API.
        :return: The structured JSON response (as a string) from GPT.
        """
        # Combine the "Overview" and "Reference Links" into one text block.
        overview_text = "\n".join(project_data.get("Overview", []))
        ref_links_text = "\n".join(project_data.get("Reference Links", []))
        keyDesign_text = "\n".join(project_data.get("Key Design Elements", []))
        targetAudience_text = "\n".join(project_data.get("Target Audience", []))
        pdf_content = f"Overview:\n{overview_text}\n\nReference Links:\n{ref_links_text}\n\nKey Design:\n{keyDesign_text}\n\nTarget Audience:\n{targetAudience_text}"
        
        # Call the GPT model using the provided format and instruct it to output JSON.
        completion = client.chat.completions.create(
            model="gpt-4.1",  # or "gpt-4o-mini" if available
            store=True,
            messages=[
                {
                    "role": "system",
                    "content": """"
    You are a professional assistant specializing in product and design briefs for apparel, with a focus on culturally rich and authentic storytelling.

    You will be provided with the following inputs:
    - A project overview
    - Reference links
    - Key design elements
    - Target audience description

    Your task is to:
    1. Research the topic thoroughly using the given information.
    2. Provide a detailed and insightful design plan that reflects the cultural and historical significance of the theme.
    3. Ensure that the plan aligns closely with the client's requirements and audience expectations.

    Deliver the output in **well-structured paragraph form**, avoiding lists or bullet points. The writing should feel intentional, researched, and visually descriptive — suitable for briefing a creative team or illustrator. Prioritize authenticity, relevance, and narrative depth."""

                },
                {
                    "role": "user",
                    "content": pdf_content
                }
            ]
        )
        
        # Extract and return the generated structured insights from the GPT response.
        return completion.choices[0].message.content

    with st.spinner('Creating Design Brief..'):
        structured_insights = generate_structured_design_insights(parsed_dict, client)
    #print("Structured Design Insights:\n", structured_insights)
    st.subheader("📜 Design Brief")
    st.text_area("Text from document:", structured_insights, height=400)

    promptCount = 25

    ##Generate Prompts
    def generate_prompts(project_data,structured_insights,client):    
            """
        Extracts the "Design Goals" and "What should Not be used" from project_data,
        sends them to GPT with instructions to return a structured JSON response.
        In the JSON:
        - Each design theme is given as a key and its value is a dictionary combining:
            • Design Concept
            • Artistic Approach
            • (Optionally) a list of style techniques related to that theme.
        - Additional sections like Color Palettes, Suggestions for Kids’ Designs,
            and a Conclusion are also included.
        
        :param project_data: dict containing project details with at least
        "Overview", "Reference Links", "Key Design Elements" and "Target Audience" keys.
        :param client: The client object to call the GPT API.
        :return: The structured JSON response (as a string) from GPT.
        """
            
            design_goals = "\n".join(project_data.get("Design Goals", []))
            avoid = "\n".join(project_data.get("What should NOT be used", []))
            design_constraint = "\n".join(project_data.get("Constraints", []))
            targetAudience_text = "\n".join(project_data.get("Target Audience", []))
            pdf_content = f"Design Goals:\n{design_goals}\n\nWhat should Not be used:\n{avoid}\n\nDesign Constraints:\n{design_constraint}\n\nTarget Audience:\n{targetAudience_text}\n\nDesign Brief:\n{structured_insights}"

        

            completion = client.chat.completions.create(
                model="gpt-4.1",  # or "gpt-4o-mini" if available
                store=True,
                messages=[
                    {
                        "role": "system",
                        "content": """
                            You are a senior visual designer with deep expertise in interpreting creative briefs and crafting high-quality, production-ready prompts for MidJourney.

                            Your objective is to:
                            1. Carefully analyze the provided design brief and identify relevant visual themes, stylistic references, and technical constraints.
                            2. Incorporate relevant insights from the supporting document: {structured_insights}.
                            3. Generate the most relevant, contextful prompts, high-fidelity MidJourney prompts that:
                            - Align precisely with the design brief (from {pdf_content})
                            - Reflect realistic, non-fictional contexts
                            - Are appropriate for screen printing applications
                            - Are not generic
                            - Generate only 25 prompts

                            Each prompt must strictly adhere to the following design and production constraints:
                            - Maximum of 6 solid colors (no gradients or tints)
                            - Vector image, traceable and scalable
                            - Ready for screen printing
                            - 4:5 aspect ratio
                            - Stylization in the range of 120 to 160
                            - No gradients, 3D textures, or shading
                            - No textual elements or typography
                            - Minimalist composition with low visual complexity
                            - Only floating objects (no backgrounds or frames)
                            - Plain background with zero detail
                            - Minimum 0.5mm line width
                            - Clear and concise subject representation
                            - Stylized with low-detail highlights only (if any)

                            **If a prompt contains the `--style` parameter, replace it with `--stylize`.**

                            ### Output Format:
                            Return your response in the following structured format:

                            {
                            "Prompts": [
                                { "Prompt 1": "[MidJourney-compatible prompt string]" },
                                                       ]
                            }

                            **Guidelines:**
                            - Think like a professional designer with a strong sense of practicality.
                            - Avoid imaginative or fictional elements that don't align with real-world constraints.
                            - Keep the prompts efficient, clear, and engineered to produce consistent, print-ready visual outputs.
                            - Ensure all elements are compliant with screen printing limitations.

                            Deliver only the JSON-formatted response. Do not include explanations or commentary.
                        """
                    },
                    {
                        "role": "user",
                        "content":pdf_content
                    }
                ]
            )


            return completion.choices[0].message.content

    with st.spinner('Generating Prompts..'):
        prompts = generate_prompts(parsed_dict,structured_insights,client)
    promptList = prompts
    #print(promptList)

    #st.subheader("📜 Prompts")
    #st.text_area("Text from document:", promptList, height=400)


    import json

    # 1) If promptList is a JSON string, parse it; otherwise assume it's already a dict
    if isinstance(promptList, str):
        data = json.loads(promptList)
    else:
        data = promptList

    # 2) Now data["Prompts"] is a real list of single‑key dicts
    #    Extract the one value from each dict
    prompt_list = [list(item.values())[0] for item in data["Prompts"]]

    st.markdown("### Prompts:")
    st.markdown("\n".join([f"{i+1}. {item}" for i, item in enumerate(prompt_list)]))

    data = prompt_list

    # 2) Convert into a list of payload dicts
    payloads = [{"prompt": prompt} for prompt in data]

    import http.client
    import json
    import time
    import pprint

    # === Configuration ===

    connection = http.client.HTTPSConnection("cl.imagineapi.dev")

    new_var = os.getenv('MJ_KEY')

    print("MJ kEYS: ",new_var)
    headers = {
        'Authorization': new_var,  
        'Content-Type': 'application/json'
    }

    response_data = {}  
    upscaled_urls = []
    prompt_id = []

    # List of prompts to process
    prompts = prompt_list


    import time

    # Function to send API requests
    def send_request(method, path, body=None, headers={}):
        conn = http.client.HTTPSConnection("cl.imagineapi.dev")
        conn.request(method, path, body=json.dumps(body) if body else None, headers=headers)
        response = conn.getresponse()
        data = json.loads(response.read().decode())
        conn.close()
        return data

    payloads = [{"prompt": prompt} for prompt in prompts]
    # for payload in payloads:
    #     print(payload)
    # Send initial image generation request


    def check_image_status(prompt_id):
        global upscaled_urls

        response_data = send_request('GET', f"/items/images/{prompt_id}", headers=headers)

        if response_data['data']['status'] in ['completed', 'failed']:
            print(f"✅ Image generation completed for prompt ID {prompt_id}:")
            pprint.pp(response_data['data'])

            # Save the upscaled URLs if they exist
            if "upscaled_urls" in response_data['data'] and isinstance(response_data['data']['upscaled_urls'], list):
                upscaled_urls.append(response_data['data']['upscaled_urls'])
                print("🔗 Collected URLs so far:", upscaled_urls)

            return True
        else:
            print(f"⏳ Prompt ID {prompt_id} is still generating. Status: {response_data['data']['status']}")
            return False

    # Main loop for sending prompts and checking their status
    for i, data in enumerate(payloads):
         
        # Submit prompt
        prompt_response_data = send_request('POST', '/items/images/', data, headers)
        pprint.pp(prompt_response_data)
        prompt_id.append(prompt_response_data['data']['id'])
        if (i + 1) % 8 == 0:
            time.sleep(10)

        # Extract prompt ID
    


    st.subheader("📜 Image Generation Status")

    # Create an empty placeholder for status updates.
    status_placeholder = st.empty()
    status = status_placeholder.status("Creating Images...", expanded=True)

    # Iterate over each prompt ID and check for the image status
    for id in prompt_id:
        while not check_image_status(id):
            time.sleep(3)  # Check every 3 seconds

        # As soon as the image is ready, update the status and display the result
        status_placeholder.write(f"✅ Done! Image for prompt ID: `{id}` completed.")

    # Update the status after all images are created
    status.update(label="All images created!", state="complete")
    import math
    # Now, render the images for each upscaled URL.
    for idx, group in enumerate(upscaled_urls):
        with st.container():
            st.subheader(f"Prompt {idx + 1}:") 
            st.write(f"{prompt_list[idx]}")

            num_per_row = 4
            num_rows = math.ceil(len(group) / num_per_row)

            for i in range(num_rows):
                row_imgs = group[i*num_per_row:(i+1)*num_per_row]
                cols = st.columns(len(row_imgs))
                for col, url in zip(cols, row_imgs):
                    with col:
                        st.image(url, use_container_width=True)
                        st.caption(f"Image {group.index(url) + 1}")

        st.divider()

    

    #save in google drive

    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = None

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If no valid creds, go through browser flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str('credentials.json'), SCOPES)
            # make sure you've added http://localhost:8080/ as an Authorized redirect URI
            creds = flow.run_local_server(host='localhost', port=8080)
            # Save for next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('drive', 'v3', credentials=creds)

    # file_metadata = {'name': 'Container.png'}
    # media = MediaFileUpload('Container.png', mimetype='image/png')
    # file = service.files().create(
    #     body=file_metadata,
    #     media_body=media,
    #     fields='id'
    # ).execute()
    # print(f'Uploaded File ID: {file.get("id")}')

    def get_folder_id(name):
        query = (
            f"name = '{name}' "
            "and mimeType = 'application/vnd.google-apps.folder' "
            "and trashed = false"
        )
        results = service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()
        items = results.get('files', [])
        if not items:
            raise FileNotFoundError(f"No folder named '{name}' found.")
        # Return the first match
        return items[0]['id']

    projects_id = get_folder_id('projects')
    print("Projects folder ID:", projects_id)

    #creating sub folder 
    def create_subfolder(name, parent_id):
        metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = service.files().create(
            body=metadata,
            fields='id'
        ).execute()
        return folder.get('id')

    # Example: create a folder named with today’s date
    import datetime
    new_folder_name = project_name
    new_folder_id = create_subfolder(new_folder_name, projects_id)
    print("Created subfolder ID:", new_folder_id)


    def upload_image_url_to_drive(service, url, folder_id, name):
    # 1) Fetch and open
        resp = requests.get(url)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content))

        # 2) Ensure PNG mode
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")

        # 3) Serialize to in-memory PNG
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        # 4) Derive filename
        filename = name or (Path(url).stem + ".png")

        # 5) Build metadata and upload
        metadata = {"name": filename}
        if folder_id:
            metadata["parents"] = [folder_id]
            media = MediaIoBaseUpload(buf, mimetype="image/png", resumable=True)
            created = service.files().create(body=metadata, media_body=media, fields="id,name").execute()
            return created["id"]

    # Assume you’ve already run your OAuth flow and have `service`:
    # service = get_drive_service_oauth()

    print("URLS:",upscaled_urls)
    flat_urls = [url for sublist in upscaled_urls for url in sublist]

    import random
    for url in flat_urls:
        # unique_name = f"{random.randint(0, 0xFFFFF):05X}"
        # unique_name = str(unique_name)
        parts = url.split('/')
        folder = parts[-2]
        filename = parts[-1].split('.')[0]
        unique_name = f"{folder}_{filename}"
        file_id = upload_image_url_to_drive(service, url, new_folder_id, str(unique_name))
        print(f"Uploaded {url} → Drive file ID {new_folder_id}")
