# RainbowBrackets

[![License][license-image]](/LICENSE)
[![Downloads][packagecontrol-image]][packagecontrol-link]

[English](README.md)


嗨，欢迎你的到来，现在容我自我介绍一下。


## 人生三问

- 你叫什么名字？
  您好，我叫**彩虹括号**，`RainbowBrackets`是我的英文名。

- 你为何而生？
  您好，我为`SublimeTex3`而生，`SublimeText3`就是我的整个世界。

- 你能做什么？
  您好，我的职责是为用户提供括号高亮服务。我能给他们粉刷括号，让括号看起来像一道道彩虹。办公室没有阳光，但你可以有彩虹。

作为一个爱美的`plugin`，让我首先为您展现一下我绚丽的英姿。
![我的靓照](images/material-scheme.png)


## 请我回家吃饭，让我为您工作

作为一个信息生命体，您可以随意把我打包带走。但是如果要让我为您工作，我需要一定的工作空间。其实很简单，让我们开始吧。

### 如何把我带回家

- 我现在注册了`Package Control`，你可以使用它提供的安装服务。
  采用这种方式，您只需要打开`SublimeText`的`命令面板`（<kbd>ctrl+shift+p</kbd>），然后输入`pcip`，选择`Package Control: Install Package`。然后请您稍等（它在传送乘客信息），等一小段时间之后，你就可以从他的乘客之中找到我了。请记得输入我的名字，无需全名，能够筛选出我就行。

- 如果`Git`是您的管家朋友的话，您可以让它为你把我带回家。
  具体具体步骤是，
  1. 打开`SublimeText`的插件目录，在此目录下打开一个终端。
  2. 运行下面命令
    ```shell
    git clone https://github.com/absop/RainbowBrackets.git
    ```
- 点击我的Github主页的绿色按钮`clone or download`，浏览器会为您把我打包进行运输，之后您需要把我解包，然后放置在`SublimeText`的插件目录，我会在那里为您工作。


## 添加设置，让我为您工作
  我能够为使用各种语言的形形色色的人提供服务，所以您需要告诉我，您使用那些语言。
  我能够为各式各样的括号提供粉刷服务，因此您需要告诉我您需要粉刷那些括号，最好是根据语言来，这样我可以更专一地工作，因而效率更高。

### 括号设置

```json
{
    "brackets": {
        "pairs": {
            "(": ")",
            "[": "]",
            "{": "}"
        },

        "filetypes": {
            "default": {
                "opening": ["(", "[", "{"],
                "ignored_scopes": [
                    "comment", "string"
                ]
            },

            "json": {
                "opening": ["[", "{"],
                "ignored_scopes": [
                    "comment", "string"
                ],
                "extensions": [
                    "json",
                    "sublime-settings",
                    "sublime-menu",
                    "sublime-build",
                    "sublime-keymap",
                    "sublime-commands",
                    "sublime-theme",
                    "sublime-color-scheme"
                ]
            }
        }
    }
}
```



上面是一个设置示例，将所有您需要进行粉刷的括号对像示例里面那样成对地放置在`"brackets"`的`"pairs"`里面，我会在`"pairs"`里面查找与开括号对应的闭括号。

您可以在`"filetypes"`里面添加默认设置和语言特定的设置，下面是各项设置的说明：

- `opening`

  每一个文件类型需要添加一个`opening`（开括号）列表，用来确定该文件类型需要粉刷那些括号，如果没有，就会使用`default`中的`opening`列表。`opening`列表中放置的开括号必须能够在`"pairs"`里面找到，这样才能确定它对应的闭括号。

- `extensions`

  添加一个文件类型时，您可以为它添加一个后缀名列表（默认设置`default`中不需要）。这样，当你打开一个新文件时，我会首先根据该文件所使用的`sublime-syntax`文件去判断它属于哪个文件类型，如果没有找到`sublime-syntax`对应的文件类型，我会继续拿它的后缀名去判断它的文件类型。最后，如果在您的设置中找到了它的文件类型，我就会按照相应的设置为您粉刷该文件中的括号；如果没有找到，你依然可以通过命令来使用`default`中的设置，后面会为您介绍各项命令及其使用。

- `ignored_scopes`，每一个文件类型都需要一个`ignored_scopes`列表，用来判断需要跳过的内容，比如`注释`和`字符串`。如果没有该列表，就会使用`default`中的相应的设置。

### 颜色设置

```json
	"rainbow_colors": {
        "matched": [
            "#FF0000",   /* level1  */
            "#FF6A00",   /* level2  */
            "#FFD800",   /* level3  */
            "#00FF00",   /* level4  */
            "#0094FF",   /* level5  */
            "#0041FF",   /* level6  */
            "#7D00E5"    /* level7  */
        ],
        "mismatched": "#FF0000"
    }
```

您可以修改`rainbow_colors`设置来改变用来粉刷括号的颜色，其中`matched`是一个颜色列表，你可以根据自己的需求修改其中的颜色，也添加或去除其中的颜色。粉刷括号时，括号的层次会以颜色数目作为一个循环。

### debug 设置

如果您将`debug`设置为`true`，则每当我为您粉刷一个文件时，我会在`SublimeText`的控制台打印一些调试信息。这些信息包括文件名、用来匹配括号的模式串和通过`ignored_scopes`生成的`selector`。您可以通过命令来开启或关闭这个选项，下面是命令使用说明。

## 随时等候您的命令

我的开发者为我编写了4个可供您呼唤的命令，它们分别是：

- `RainbowBrackets: toggle debug`

  默认情况下，我并不会为您打印调试信息。您可以通过这个命令来开启或关闭调试信息。

- `RainbowBrackets: make rainbow`

  前面讲到，您可以通过命令，在一个我没有为之工作的文件中呼唤我为您工作。通过此命令，我可以为您在包括您没有添加到设置的所有文件类型中工作，我会首先去匹配设置中的文件类型，然后在没有找到的情况下使用`default`中的设置。

- `RainbowBrackets: clear rainbow`

  如果您想要在某个大型文件中扔掉我这个包袱，您可以使用这个命令。

- `RainbowBrackets: clear color schemes`

  当您切换`Color Scheme`时，我会在您的`Packages/User/Color Schemes/RainbowBrackets`目录下生成对应的`Color Scheme`，用来为括号着色，您可以使用这个命令来清除它们。

  

## 晒照

最后，为了开启我快乐的工作旅程，容我再晒两张靓照。

- ![Scheme，括号神教](images/material-lighter.png)
- ![JSON，小巧优雅的数据交换格式](images/material-json.png)


[license-image]: https://img.shields.io/badge/license-MIT-blue.svg
[packagecontrol-image]: https://img.shields.io/packagecontrol/dt/RainbowBrackets.svg
[packagecontrol-link]: https://packagecontrol.io/packages/RainbowBrackets
