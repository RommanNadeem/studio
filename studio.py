

import sys
import streamlit as st
from openai import OpenAI
from docx import Document
import fitz
import json
import http.client
import pprint
import time 
from io import StringIO
from docx import Document
import PyPDF2
import os
from dotenv import load_dotenv
load_dotenv()



client = OpenAI(
  api_key= os.getenv("OPENAI_KEY")
)


st.set_page_config(page_title="📄 Document Reader", layout="centered")

st.title(":blue[Studio Stream]")


uploaded_file = st.file_uploader("upload a document to begin", type=["pdf", "docx", "txt"])

while not uploaded_file:
    def read_pdf(file):
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text


def read_docx(file):
    doc = Document(file)
    return "\n".join([para.text for para in doc.paragraphs])

def read_txt(file):
    stringio = StringIO(file.getvalue().decode("utf-8"))
    return stringio.read()

if uploaded_file is not None:
    file_type = uploaded_file.name.split(".")[-1].lower()

    if file_type == "pdf":
        content = read_pdf(uploaded_file)
    elif file_type == "docx":
        content = read_docx(uploaded_file)
    elif file_type == "txt":
        content = read_txt(uploaded_file)
    else:
        st.error("Unsupported file type.")
        content = ""



    # st.subheader("📜 Document Content")
    # st.text_area("Text from document:", content, height=400)




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
- --ar 4:5 --stylize 200 --quality 2
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
                        You are an expert visual designer with a deep understanding of interpreting design briefs and translating them into MidJourney prompts.

                        Your task is to:
                        1. Read and understand the provided design brief and extract relevant visual themes, style references, and constraints from it.
                        2. use the research from the file {structured_insights}
                        3. Generate unique, high-quality MidJourney prompts that strictly follow the design guidelines outlined in {pdf_content} and close to reality in terms of context. No fiction.
                        4. Ensure that each prompt is:
                        - Visually descriptive and contextually relevant
                        - Formatted for MidJourney's syntax
                        - Screen print ready and adheres to all constraints mentioned in the brief (e.g. aspect ratio, color limits, shading rules, no gradients, etc.)
                        - Clear, concise, and structured to inspire consistent visual outputs
                        - Add clear guideline to add no textual element in the design.
                        5.Ensure each prompt has the following constraints included
                        - 6 colours maximum
                        - Vector image traceable
                        - Screen print ready
                        - 4:5 ratio
                        - style in range of 120-160
                        - No gradients
                        - No 3D textures
                        - No textual elements
                        - Only low detail shading and highlights
                        - Floating objects 
                        - no frames
                        - no backgrounds at all
                        - .5mm line widths at a minimum
                        - Low complexity
                        - Minimalist artwork
                        - Solid colours, no tints
                        - no shading
                        - vector images,
                        - make sure it is low details.
                        - make sure there is no background detail at all! 
                        - plane background

                        Return your output in the following list format:
                        {
                        "Prompts": [
                            {
                            "Prompt 1": "[MidJourney-compatible prompt string based on the design brief]"
                            },
                            {
                            "Prompt 2": "[MidJourney-compatible prompt string based on the design brief]"
                            },
                        ]
                        }
         Think like a designer. Be creative but bounded by the brief. Every prompt must respect the technical and artistic constraints.

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
st.markdown("\n".join([f"- {item}" for item in prompt_list]))

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
for data in payloads:
    # Submit prompt
    prompt_response_data = send_request('POST', '/items/images/', data, headers)
    pprint.pp(prompt_response_data)

    # Extract prompt ID
    prompt_id.append(prompt_response_data['data']['id'])
print(prompt_id)


st.subheader("📜 Image Generation Status")
with st.status("Creating Images...", expanded=True) as status:
    for id in prompt_id:
        st.write(f"🟡 Generating image for prompt ID: `{id}`")

        while not check_image_status(id):
            st.write(f"⏳ Still processing prompt ID: `{id}`...")
            time.sleep(3)

        st.write(f"✅ Done! Image for prompt ID: `{id}` completed.")
    
    status.update(label="All images created!", state="complete")
# After all prompts are processed
# print("\n🎉 All done! Final list of upscaled image URLs:")
# pprint.pp(upscaled_urls)


# st.markdown("### URLs:")
# st.markdown("\n".join([f"- {item}" for item in upscaled_urls]))

# for idx, group in enumerate(upscaled_urls):
#     st.subheader(f"Prompt {idx + 1}:") 
#     st.write(f"{prompt_list[idx]}")
#     cols = st.columns(len(group))  # create a column for each image
#     for col, url in zip(cols, group):
#         with col:
#             st.image(url, use_container_width=True)
    
import math

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
