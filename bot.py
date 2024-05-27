

import discord
from discord.ext import commands
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote
from io import BytesIO
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas
from PIL import Image
import os
import aiohttp
import asyncio

intents = discord.Intents.default()
intents.typing = False
intents.presences = False
intents.message_content = True

bot = commands.Bot(command_prefix='', intents=intents)  # No prefix
TARGET_CHANNEL_ID = [1216390539423912047]
slideshare_link_pattern = r'(https?://www\.slideshare\.net/\S+)'

async def handle_slideshare_links(message):
    if message.channel.id in TARGET_CHANNEL_ID:
        urls = re.findall(slideshare_link_pattern, message.content)
        if urls:
            tasks = []
            for url in urls:
                tasks.append(process_link(message, url))
            await asyncio.gather(*tasks)

async def process_link(message, url):
    loading_message = await message.reply("Please wait. We are retrieving your files :hourglass_flowing_sand:")
    try:
        image_links, total_pages = await process_url(url)
        filtered_links = [link for link in image_links if '-1-2048.jpg' in link]
        if filtered_links:
            modified_links_sent = set()
            for link in filtered_links:
                for page_num in range(1, total_pages + 1):
                    modified_link = link.replace('-1-', f'-{page_num}-')
                    if modified_link not in modified_links_sent:
                        modified_links_sent.add(modified_link)
            modified_downloaded_images = await download_images(modified_links_sent, total_pages)
            if modified_downloaded_images:
                pdf_filename = 'slides.pdf'
                modified_downloaded_images.sort(key=sort_images)
                create_pdf(modified_downloaded_images, pdf_filename)
                await send_pdf_link(message.channel, pdf_filename, message, url)
                for image_file in modified_downloaded_images:
                    os.remove(image_file)
            else:
                await message.channel.send("No images found on the provided URL.")
        else:
            await message.channel.send("No valid image links found on the provided URL.")
    except Exception as e:
        await message.channel.send(f"An error occurred: {str(e)}")
    finally:
        await loading_message.delete()

# Function to process the URL and extract image links
async def process_url(url):
    image_links = []
    total_pages = None

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                text = await response.text()
                soup = BeautifulSoup(text, 'html.parser')
                page_number_element = soup.find('span', {'data-cy': 'page-number'})
                if page_number_element:
                    total_pages = int(re.search(r'of (\d+)', page_number_element.text).group(1))
                    for img_tag in soup.find_all('img', {'class': 'vertical-slide-image'}):
                        srcset = img_tag.get('srcset')
                        if srcset:
                            links = re.findall(r'https?://[^\s,]+', srcset)
                            image_links.extend(links)

    return image_links, total_pages

# Function to download images
async def download_images(image_links, total_pages):
    downloaded_images = []
    async with aiohttp.ClientSession() as session:
        tasks = []
        for link in image_links:
            tasks.append(download_image(session, link))
        results = await asyncio.gather(*tasks)
        for result in results:
            if result:
                downloaded_images.append(result)
    return downloaded_images

async def download_image(session, link):
    match = re.search(r'-(\d+)-2048.jpg', link)
    if match:
        page_num = int(match.group(1))
        filename = f'image{page_num}.jpg'
        async with session.get(link) as response:
            if response.status == 200:
                with open(filename, 'wb') as f:
                    f.write(await response.read())
                return filename
    return None

# Function to create PDF
def create_pdf(image_files, pdf_filename):
    c = canvas.Canvas(pdf_filename, pagesize=landscape(letter))
    for image_file in image_files:
        image_path = f"{os.getcwd()}/{image_file}"
        img = Image.open(image_path)
        img_width, img_height = img.size
        c.setPageSize((img_width, img_height))
        c.drawInlineImage(image_path, 0, 0)
        c.showPage()
    c.save()

# Custom sorting function for image filenames
def sort_images(image_file):
    match = re.search(r'image(\d+).jpg', image_file)
    if match:
        return int(match.group(1))
    return 0

# Function to send the link of the uploaded PDF file
async def send_pdf_link(channel, pdf_filename, message, url):
    with open(pdf_filename, 'rb') as f:
        files = {'file': f}
        async with aiohttp.ClientSession() as session:
            async with session.post('https://file.io/', data=files) as response:
                response_data = await response.json()
                if response.status == 200:  # Check if upload was successful
                    link = response_data['link']
                    embed = discord.Embed(
                        title="Slideshare File Unlocked",
                        description="Your file link is here.",
                        color=0x86ff00
                    )
                    embed.add_field(name="Question", value=f"[Click here]({url})", inline=False)
                    embed.add_field(name="Answer", value=f"[Click here]({link})", inline=False)
                    embed.set_footer(text="Powered by UWorkify.com | Made by AW")
                    embed.set_thumbnail(
                        url="https://cdn.discordapp.com/attachments/847880723289342003/847881117365567568/70a552e8e955049c8587b2d7606cd6a6.gif"
                    )
                    mention = message.author.mention
                    reply_content = message.author.mention
                    avatar_url = message.author.avatar.url if message.author.avatar else None
                    embed.set_author(name=message.author.name, icon_url=avatar_url)

                    await message.reply(reply_content, embed=embed)
                    os.remove(pdf_filename)  # Delete the PDF file after successful upload
                else:
                    await message.channel.send("An error occurred while uploading the file.")


@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await handle_slideshare_links(message)


bot.run('MTE3Mjg0Mjk3OTU1MjE1MzY5MQ.GdsKFr.MnBAmPBuYTdO9yjxnkIVnJ5ZeayDg_qSLANvfo')
