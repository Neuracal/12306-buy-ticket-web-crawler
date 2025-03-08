# 12306-buy-ticket-web-crawler

这里是一个可以在12306购票的脚本程序，主要采用Python中的requests库来爬取12306网页信息，并提交相关参数，从而成功购票。

## 文件说明

购票时需要运行的程序只有`12306_buyTickets.py`。

`station_code.py`用于获得全国所有火车站的站名和其电报码的对应关系，如“上海虹桥”站的电报码为“AOH”。`station_code.txt`和`station_code.xlsx`都是火车站站名和电报码的对应文件，有这样两个文件存放相同内容的数据，只是为了好看而已。由于12306购票时，网页提交的与火车站有关的参数，大多不是车站名，而是车站的电报码，所以必须首先获得车站名和电报码的对应关系。

**运行脚本的顺序为：先运行`station_code.py`以获得`station_code.xlsx`，再运行`12306_buyTickets.py`购票。由于本仓库已经给出`station_code.xlsx`，所以仅运行`12306_buyTickets.py`而不用运行`station_code.py`也是可以的。**

整个程序的购票步骤可以分为以下几个部分：

1. **登录**。如果之前有登录过，存下了`cookie.txt`，那么可以直接读取其中的cookie免二维码扫描地登录。如果没有存下`cookie.txt`或者cookie已经过期，那么程序会生成登录二维码（相当于12306网页版的“扫码登录”）`login.png`。用户用登录了自己账号的12306手机APP扫描这个二维码即可成功登录到12306网站。

> `cookies.txt`和`login.png`默认都存放在`12306_buyTickets.py`的同级目录中。

2. 