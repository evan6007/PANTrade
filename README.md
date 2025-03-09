![Premium Bread](https://github.com/evan6007/Trade/blob/main/panbanner.png?raw=true)

# AWS EC2 環境設置與運行指南

本指南將帶你從零開始在 AWS EC2 上設置環境，並運行程式。

## 1. 建立 AWS EC2

1. 前往 AWS EC2 主控台：[AWS EC2 Console](https://ap-southeast-2.console.aws.amazon.com/ec2/home?region=ap-southeast-2#Home)
2. 建立一個新的 EC2 實例
   - AMI 選擇 **Ubuntu**
   - 其他配置依照需求設定

## 2. 連接 EC2

請參考以下教學來使用 VSCode 連接 EC2：
[如何用 VSCode 連接 EC2](https://www.youtube.com/watch?v=elkL1OF9fxI)

## 3. 更新系統並安裝必要工具

在 EC2 中執行以下指令：
```sh
sudo apt update
sudo apt upgrade -y
```

## 4. 安裝 Git、Tmux 及 Python 相關工具
```sh
sudo apt install git -y   # 安裝 Git
sudo apt install tmux -y  # 安裝 Tmux
sudo apt install python3-pip -y
```

## 5. 建立虛擬環境

```sh
sudo apt install -y python3 python3-pip
sudo apt-get install python3.12-venv
python3 -m venv myenv  # 創建虛擬環境
source myenv/bin/activate  # 啟動虛擬環境
```

## 6. 安裝必要的 Python 套件

```sh
pip install pandas python-binance requests
```

要退出虛擬環境時，執行：
```sh
deactivate
```

## 7. 使用 Tmux 管理工作環境

```sh
tmux  # 啟動 Tmux
```

## 8. 執行專案

請依照以下步驟執行程式：

1. **啟動虛擬環境**
    ```sh
    source myenv/bin/activate
    ```
2. **切換到 Trade 目錄**
    ```sh
    cd Trade
    ```
3. **開始運行程式**
    ```sh
    python your_script.py  # 替換成你的主程式
    ```
4. **把API KEY存IP**
   去幣安 把IP給ＡＰＩ的權限

這樣你的環境就設定完成了！🚀

