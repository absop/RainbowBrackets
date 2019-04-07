# RainbowBrackets


## Introduction
This is a plugin I wrote for **SublimeText** to highlight
brackets, it matches the brackets, and then gives the brackets
different colors for different layers. like a rainbow.

Note that this plugin is available for all color schemes, whether
they are in tmTheme format or sublime-color-scheme format, so you
can change the color scheme at will.


## Installation
Clone or download this repository to your SublimeText's **Packages** directory.
Note that the directory name should be the name of this repository.


## Usage

### Working mode
The rainbower has two mode for rainbowing brackets matched.
- The mode **all** will highlight all brackets matched in the `View`.
  In this case, editing a very large file maybe cause some delay.

- The mode **part** will only highlight brackets around the cursor,
  with a threshold for the number of characters to be searched.
  Not applicable to multiple cursor editing.

### Colors
Colors for highlighting matched brackets are stored in a array with
a variable number of colors. You can add any number of colors, The
plugin will loop use each color in the array.

### More language support
This plugin is designed and developed for scheme language,
but it doesn't only support scheme. To support your own language,
please refer to the original configuration and add your own language
to the Settings file.


## Screenshots
- Material color scheme, Json
  ![material-color-scheme, Json](https://github.com/absop/RainbowBrackets/images/material-json.png)
- Material color scheme, Scheme
  ![material-color-scheme, Scheme](https://github.com/absop/RainbowBrackets/images/material.png)
- Material-lighter, Scheme
  ![material-lighter-color-scheme, Scheme](https://github.com/absop/RainbowBrackets/images/material-lighter.png)
