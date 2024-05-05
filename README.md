# AI Testing Tool

## Demo

The test case is 

```
When you add a google account in Passwords & accounts, username is abc@gmail.com, password is 123456. Then you should see an error "Couldn't find your Google Account".
```

![](https://images.shangjiaming.top/ai-testing-tool-5x-demo.gif)

## Architecture

![](https://images.shangjiaming.top/QA%20POC_2024-05-03_14-13-58.png)
![](https://images.shangjiaming.top/ai-testing-tool-sequence-diagram.png)

## How to use it?

Run the following command to run the tool

```sh
OPENAI_API_KEY=<openai api key> python ai-testing-tool.py <system prompt file> <task file> --appium=<appium server address>
```

Run the following command to run the tool in debug mode

```sh
python ai-testing-tool.py <system prompt file> <task file> --appium=<appium server address> --debug
```

## Acknowledgements

1. https://github.com/Nikhil-Kulkarni/qa-gpt
2. https://github.com/quinny1187/GridGPT
3. https://github.com/nickandbro/chatGPT_Vision_To_Coords
4. https://arxiv.org/abs/2304.07061