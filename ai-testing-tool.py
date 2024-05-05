import argparse
import datetime
import json
import os
import threading
from openai import OpenAI
import base64
from time import sleep
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from PIL import Image, ImageDraw, ImageFont
import xml.etree.ElementTree as ET
import yaml


def read_file_content(file_path):
    try:
        with open(file_path, "r") as file:
            content = file.read()
        return content
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' does not exist.")
    except IOError:
        print(f"Error: Unable to read the file '{file_path}'.")


def create_folder(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    return folder_path


def image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def generate_next_action(
    prompt, task, history_actions, page_source_file, page_screenshot
):
    screenshot_base64 = image_to_base64(page_screenshot)
    page_source = read_file_content(page_source_file)
    history_actions_str = "\n".join(history_actions)
    messages = []
    messages.append({"role": "system", "content": prompt})
    messages.append(
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"# Task \n {task}"},
                {
                    "type": "text",
                    "text": f"# History of Actions \n {history_actions_str}",
                },
                {
                    "type": "text",
                    "text": f"# Source of Page \n ```yaml\n {page_source} \n```",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{screenshot_base64}"},
                },
            ],
        }
    )

    openAI = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    chat_response = openAI.chat.completions.create(
        model="gpt-4-turbo", messages=messages, max_tokens=200
    )

    content = chat_response.choices[0].message.content
    return content


def create_driver(appium_server):
    capabilities = dict(
        platformName="Android",
        automationName="uiautomator2",
        deviceName="Android",
        # appPackage="com.android.settings",
        # appActivity=".Settings",
        language="en",
        locale="US",
    )

    return webdriver.Remote(
        appium_server,
        options=UiAutomator2Options().load_capabilities(capabilities),
    )


def resize_image(img, max_long=2048, max_short=768):
    """Resize the image maintaining aspect ratio"""
    original_width, original_height = img.size
    aspect_ratio = original_width / original_height

    if aspect_ratio > 1:
        new_width = min(original_width, max_long)
        new_height = int(new_width / aspect_ratio)

        new_height = min(new_height, max_short)
        new_width = int(new_height * aspect_ratio)

    else:
        new_height = min(original_height, max_long)
        new_width = int(new_height * aspect_ratio)

        new_width = min(new_width, max_short)
        new_height = int(new_width / aspect_ratio)

    return img.resize((new_width, new_height))


def draw_grid_with_labels(image_path, grid_size, output_path):
    # Open an image file
    with Image.open(image_path) as img:
        width, height = img.size

        # Calculate needed space for labels based on grid size
        label_space = 30  # adjustable based on font size

        # Create a new image with extra space for labels
        new_width = width + label_space
        new_height = height + label_space
        new_img = Image.new("RGB", (new_width, new_height), "white")
        new_img.paste(img, (label_space, label_space))

        draw = ImageDraw.Draw(new_img)

        # Load a font
        try:
            # Adjust the path to the font file according to your system or use a basic PIL font
            font = ImageFont.truetype("arial.ttf", 14)
        except IOError:
            font = ImageFont.load_default()

        # Draw vertical lines and numbers
        for x in range(label_space, new_width, grid_size):
            line = ((x, label_space), (x, new_height))
            draw.line(line, fill=128)
            # Draw the number shifted slightly to the left of the line
            draw.text(
                (x - 5, 5), str((x - label_space) // grid_size), fill="black", font=font
            )

        # Draw horizontal lines and numbers
        for y in range(label_space, new_height, grid_size):
            line = ((label_space, y), (new_width, y))
            draw.line(line, fill=128)
            # Draw the number just above the line
            draw.text(
                (5, y - 10),
                str((y - label_space) // grid_size),
                fill="black",
                font=font,
            )

        # Save the modified image
        resize_image(new_img).save(output_path)


def format_image(image_path, output_path):
    # Open an image file
    with Image.open(image_path) as img:
        width, height = img.size

        new_img = Image.new("RGB", (width, height), "white")
        new_img.paste(img)

        resize_image(new_img).save(output_path)


def write_to_file(file_path, string_to_write):
    with open(file_path, "w") as file:
        file.write(string_to_write)
    return file_path


def write_to_file_with_line_filter(file_path, string_to_write, filter):
    filtered_lines = [
        line.strip() for line in string_to_write.split("\n") if filter in line
    ]
    with open(file_path, "w") as file:
        file.write("\n".join(filtered_lines))
    return file_path


def remove_unexpected_attr(node):
    unexpected_keys = [
        key
        for key, value in node.attrib.items()
        if key
        not in [
            "index",
            "package",
            "class",
            "text",
            "resource-id",
            "content-desc",
            "clickable",
            "scrollable",
            "bounds",
        ]
    ]
    for key in unexpected_keys:
        del node.attrib[key]
    for child in node:
        remove_unexpected_attr(child)


def refine_xml(xml_str):
    root = ET.fromstring(xml_str)
    remove_unexpected_attr(root)
    return ET.tostring(root, encoding="unicode")


def xml_to_dict(xml_element: ET.Element):
    result = {}
    for child in xml_element:
        child_dict = xml_to_dict(child)
        if child_dict:
            if child.tag in result and result[child.tag]:
                result[child.tag].append(child_dict)
            else:
                result[child.tag] = [child_dict]

    if xml_element.text and xml_element.text.strip():
        text = xml_element.text.strip()
        if "content" in result and result["content"]:
            result["content"].append(text)
        else:
            result["content"] = [text]

    expected_attrib = {
        (key, value)
        for key, value in xml_element.attrib.items()
        if key
        in [
            "index",
            "package",
            "class",
            "text",
            "resource-id",
            "content-desc",
            "clickable",
            "scrollable",
            "bounds",
        ]
        and value.strip()
    }
    if expected_attrib:
        result.update(expected_attrib)
    return result


def xml_to_yaml(xml_file, yaml_file):
    root = ET.fromstring(read_file_content(xml_file))
    xml_dict = xml_to_dict(root)
    yaml_data = yaml.dump(xml_dict, default_flow_style=False)
    return write_to_file(yaml_file, yaml_data)


def xml_str_to_yaml(yaml_file, xml_str):
    root = ET.fromstring(xml_str)
    xml_dict = xml_to_dict(root)
    yaml_data = yaml.dump(xml_dict, default_flow_style=False)
    return write_to_file(yaml_file, yaml_data)


def take_page_source(driver, folder, name):
    write_to_file(f"{folder}/{name}.xml", driver.page_source)
    return xml_str_to_yaml(f"{folder}/{name}.yaml", driver.page_source)


def take_screenshot(driver: webdriver.Remote, folder, name):
    driver.save_screenshot(f"{folder}/{name}.png")
    format_image(f"{folder}/{name}.png", f"{folder}/{name}.jpg")
    return f"{folder}/{name}.jpg"


def parse_bounds(bounds):
    left_top, right_bottom = bounds.split("][")
    left, top = map(int, left_top[1:].split(","))
    right, bottom = map(int, right_bottom[:-1].split(","))
    return (left, top, right, bottom)


def process_next_action(action, driver: webdriver.Remote, folder, step_name):
    data = json.loads(action)

    if data["action"] == "error" or data["action"] == "finish":
        take_page_source(driver, folder, step_name),
        take_screenshot(driver, folder, step_name),
        data["result"] = "success"
        return (None, None, json.dumps(data))
    else:
        if data["action"] == "tap" and "bounds" in data:
            bounds = data["bounds"]
            left, top, right, bottom = parse_bounds(bounds)
            tap_x = left + (right - left) / 2
            tap_y = top + (bottom - top) / 2
            driver.tap([(tap_x, tap_y)])
            data["result"] = "success"
        elif data["action"] == "tap" and "xpath" in data:
            xpath = data["xpath"]
            elements = driver.find_elements(by=AppiumBy.XPATH, value=xpath)
            if elements:
                elements[0].click()
                data["result"] = "success"
            else:
                data["result"] = f"can't find element {xpath}"
                print(f"Can't find element {xpath}")
        elif data["action"] == "swipe":
            swipe_start_x = data["swipe_start_x"]
            swipe_start_y = data["swipe_start_y"]
            swipe_end_x = data["swipe_end_x"]
            swipe_end_y = data["swipe_end_y"]
            duration = data["duration"]
            driver.swipe(
                swipe_start_x, swipe_start_y, swipe_end_x, swipe_end_y, duration
            )
            sleep(duration / 1000)
            data["result"] = "success"
        elif data["action"] == "input" and "bounds" in data:
            bounds = data["bounds"]
            value = data["value"]
            left, top, right, bottom = parse_bounds(bounds)
            tap_x = left + (right - left) / 2
            tap_y = top + (bottom - top) / 2
            driver.tap([(tap_x, tap_y)])
            elements = driver.find_elements(
                by=AppiumBy.XPATH, value="//*[@focused='true']"
            )
            if elements:
                elements[0].send_keys(value)
                driver.hide_keyboard()
                data["result"] = "success"
            else:
                data["result"] = f"can't find element in bounds {bounds}"
                print(f"Can't find element in bounds {bounds}")
        elif data["action"] == "input" and "xpath" in data:
            xpath = data["xpath"]
            value = data["value"]
            elements = driver.find_elements(by=AppiumBy.XPATH, value=xpath)
            if elements:
                elements[0].click()
                fresh_element = driver.find_element(
                    by=AppiumBy.XPATH, value="//*[@focused='true']"
                )
                fresh_element.send_keys(value)
                driver.hide_keyboard()
                data["result"] = "success"
            else:
                data["result"] = f"can't find element {xpath}"
                print(f"Can't find element {xpath}")
        elif data["action"] == "wait":
            sleep(data["timeout"] / 1000)
            data["result"] = "success"
        else:
            print(f"unknown action, {action}")
            data["result"] = "unknown action"
            return (None, None, json.dumps(data))

        return (
            take_page_source(driver, folder, step_name),
            take_screenshot(driver, folder, step_name),
            json.dumps(data),
        )


def get_current_timestamp():
    now = datetime.datetime.now()
    timestamp_str = now.strftime("%Y-%m-%d-%H-%M-%S")
    return timestamp_str


def keep_driver_live(driver: webdriver.Remote):
    try:
        while driver:
            driver.page_source
            sleep(10)
    except:
        print("closing thread.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Testing Tool")
    parser.add_argument("prompt", help="Prompt file")
    parser.add_argument("task", help="Task file")
    parser.add_argument(
        "--appium",
        default="http://localhost:4723",
        help="Appium server, default is localhost:4723",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode, default is false")
    parser.add_argument(
        "--reports", default="./reports", help="Folder to store the reports, default is ./reports"
    )

    args = parser.parse_args()

    prompt_file = args.prompt
    task_file = args.task
    debug = args.debug
    reports_folder = args.reports
    appium_server = args.appium

    prompt = read_file_content(prompt_file)
    tasks = json.loads(read_file_content(task_file))

    driver = create_driver(appium_server)
    driver.implicitly_wait(0.2)
    thread = threading.Thread(target=lambda: keep_driver_live(driver))
    thread.start()

    for task in tasks:
        print(task)
        name = task["name"]
        details = task["details"]
        skip = task["skip"]
        if skip:
            print(f"skip {name}")
            continue

        task_folder = create_folder(
            f"{reports_folder}/{name}/{get_current_timestamp()}"
        )
        write_to_file(f"{task_folder}/task.json", json.dumps(task))
        sleep(1)
        page_source_for_next_step = take_page_source(driver, task_folder, "step_0")
        page_screenshot_for_next_step = take_screenshot(driver, task_folder, "step_0")
        history_actions = []
        step = 0

        while page_source_for_next_step is not None:
            step += 1
            page_source = read_file_content(page_source_for_next_step)
            history_actions_str = "\n".join(history_actions)
            prompts = [
                f"# Task \n {details}",
                f"# History of Actions \n {history_actions_str}",
                f"# Source of Page \n ```yaml\n {page_source} \n```",
            ]
            write_to_file(f"{task_folder}/step_{step}_prompt.md", "\n".join(prompts))

            if debug:
                next_action = input("next action:")
            else:
                next_action = generate_next_action(
                    prompt,
                    details,
                    history_actions,
                    page_source_for_next_step,
                    page_screenshot_for_next_step,
                )

            print(f"{step}: {next_action}")

            (
                page_source_for_next_step,
                page_screenshot_for_next_step,
                next_action_with_result,
            ) = process_next_action(next_action, driver, task_folder, f"step_{step}")
            write_to_file(f"{task_folder}/step_{step}.json", next_action_with_result)
            history_actions.append(next_action_with_result)

        driver.quit()
        driver = None
