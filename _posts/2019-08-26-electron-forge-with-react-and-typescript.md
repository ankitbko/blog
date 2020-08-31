---
layout: post
title: Electron-Forge + React + TypeScript = Awesome!
comments: true
categories: [React, TypeScript, Electron, Javascript, Electron Forge, node]
description: Setup React and TypeScript with Electron Forge
---

Recently I wanted start a new project on Electron and chose React to design UI. Having no prior experience in developing Electron App, I sat down to do some research. The [Electron Documentation](https://electronjs.org/docs/tutorial/boilerplates-and-clis) states two ways to start an electron project, **Boilerplate** or **CLI**, with a slight lean towards CLI.

The documentation mentions _React_ support with both the processes through [Electron-Forge](https://electronforge.io/)(CLI) or [electron-react-boilerplate](https://github.com/chentsulin/electron-react-boilerplate). Electron-Forge is similar to [create-react-app (CRA)](https://github.com/facebook/create-react-app) in terms of scaffolding the base solution and getting a ready-to-run application setup correctly. Having had an excellent experience with CRA before, I chose to start my project using electron-forge.

Although Electron docs mentions electron-forge has ready to use templates for React, at the time of writing [electron-forge](https://www.electronforge.io/) documentation does not list any React template nor any guide on how to setup React or TypeScript. Moreover there was surprisingly little information available on the web regarding this. Luckily I found excellent [blog by Ju Hae Lee](https://www.juhaelee.dev/TypeScript-electron/) that helped me with setting up TypeScript+React electron App using Babel. [Babel](https://babeljs.io/) is a great package in itself and I would recommend everyone to go through [this excellent article](https://iamturns.com/TypeScript-babel/) on how Babel and TypeScript works together. To summarize, the way Babel works is by _removing_ TypeScript and converting TypeScript into regular Javascript. This increases compile speed dramatically (one major complain from TypeScript) at the cost forgoing _type checking_ at build time. There are workarounds (like type-checking during test) that are described in more details in the article above and I would recommend everyone to read it. You may or may not like this approach depending upon your project and team configuration. I, myself, wanted to maintain TypeScript's type checking during build time and so decided to not configure babel. If you want to use Babel I would recommend you read Ju Lee's blog.

### Getting started with Electron-Forge

There are two ways to setup electron-forge - vanilla installation or using a template. We will setup using [Webpack template](https://www.electronforge.io/templates/webpack-template) (the only available template at the time of writing).

```sh
npx create-electron-app my-app --template=webpack
```

### Setup TypeScript

#### Install typescript

Next we are going to setup TypeScript. Run the following script -

```bash
yarn add --dev typescript ts-loader fork-ts-checker-webpack-plugin
```

We use [ts-loader](https://github.com/TypeStrong/ts-loader) as loader for webpack and [fork-ts-checker-webpack-plugin](https://github.com/TypeStrong/fork-ts-checker-webpack-plugin) for faster builds. **fork-ts-checker-webpack-plugin** will run the typescript _type checker_ in a separate process significantly increasing build time.

#### Create tsconfig.json

Since we are not using Babel, we will need to create config file for TypeScript. Create a `tsconfig.json` file in the root folder with following content.

```json
{
  "compilerOptions": {
    "target": "es5",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "esnext",
    "moduleResolution": "node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react"
  },
  "include": ["src"]
}
```

#### Webpack changes

Next we need to modify webpack configurations to load TypeScript files.

- Add the following to `webpack.rules.js`

```js
{
  test: /\.tsx?$/,
  exclude: /(node_modules|.webpack)/,
  loaders: [{
    loader: 'ts-loader',
    options: {
      transpileOnly: true
    }
  }]
}
```

- Create a new file called `webpack.plugins.js` in the root folder and put the following content. Note that I have passed `async: false` as an option to `fork-ts-checker-webpack-plugin`. This will fail the build process if there is any _type_ error. In case this slows down the build performance you can change it to `async: true`.

```js
const ForkTsCheckerWebpackPlugin = require('fork-ts-checker-webpack-plugin');

module.exports = [
  new ForkTsCheckerWebpackPlugin({
    async: false
  })
];
```

- Import this newly created plugin in the `webpack.renderer.config.js`.

```js
const rules = require('./webpack.rules');
const plugins = require('./webpack.plugins');

rules.push({
  test: /\.css$/,
  use: [{ loader: 'style-loader' }, { loader: 'css-loader' }]
});

module.exports = {
  // Put your normal webpack config below here
  module: {
    rules
  },
  plugins: plugins
};
```

### Setup React

- Install react using following script or by modifying _package.json_

```bash
yarn add react react-dom @types/react @types/react-dom
```

- Next we will create `App.tsx` file under _src_ folder which will serve as entrypoint to renderer process.

```typescript
import * as React from 'react';
import * as ReactDOM from 'react-dom';

ReactDOM.render(<div>hello world from React! </div>, document.getElementById('root'));
```

Since we don't have **root** element in our HTML, modify the `index.html` accordingly.

```html
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <title>Hello World!</title>
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
```

- Next change the _entrypoint_ under the _forge_ field for renderer in `package.json` to point to our _app.tsx_ file.

```javascript
{
  ///... other stuffs
  "config": {
    "forge": {
      ///... other stuffs
      "plugins": [
        [
          "@electron-forge/plugin-webpack",
          {
            "mainConfig": "./webpack.main.config.js",
            "renderer": {
              "config": "./webpack.renderer.config.js",
              "entryPoints": [
                {
                  "html": "./src/index.html",
                  "js": "./src/app.tsx",
                  "name": "main_window"
                }
              ]
            }
          }
        ]
      ]
    }
  }
}
```

Now run the application using `yarn start` and React should render correctly.

### Optional - setup TypeScript for Main process

We only setup TypeScript in renderer as that is most likely place where usually development happens. However if you want to use TypeScript for developing _main_ process you will need to make some additional changes

#### Main.js to Main.ts

- First rename _Main.js_ to _Main.ts_. Then replace the content in the file with the one below

```typescript
import { app, BrowserWindow } from 'electron';
declare var MAIN_WINDOW_WEBPACK_ENTRY: any;

// Handle creating/removing shortcuts on Windows when installing/uninstalling.
if (require('electron-squirrel-startup')) {
  // eslint-disable-line global-require
  app.quit();
}

// Keep a global reference of the window object, if you don't, the window will
// be closed automatically when the JavaScript object is garbage collected.
let mainWindow: any;

const createWindow = () => {
  // Create the browser window.
  mainWindow = new BrowserWindow({
    width: 800,
    height: 600
  });

  // and load the index.html of the app.
  mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY);

  // Open the DevTools.
  mainWindow.webContents.openDevTools();

  // Emitted when the window is closed.
  mainWindow.on('closed', () => {
    // Dereference the window object, usually you would store windows
    // in an array if your app supports multi windows, this is the time
    // when you should delete the corresponding element.
    mainWindow = null;
  });
};

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.on('ready', createWindow);

// Quit when all windows are closed.
app.on('window-all-closed', () => {
  // On OS X it is common for applications and their menu bar
  // to stay active until the user quits explicitly with Cmd + Q
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  // On OS X it's common to re-create a window in the app when the
  // dock icon is clicked and there are no other windows open.
  if (mainWindow === null) {
    createWindow();
  }
});

// In this file you can include the rest of your app's specific main process
// code. You can also put them in separate files and import them here.
```

We have only changed 3 lines of code. First is to replace `require` statement with `import` statement. Then declare a global variable _MAIN_WINDOW_WEBPACK_ENTRY_ as it will be initialized by webpack and contain URL for our HTML. The last step is to fix build error by explicitly setting type of variable `mainWindow` to `any`.

- Lastly change the `webpack.main.config.js` to include plugin and modify the entrypoint to _main.ts_.

```js
const plugins = require('./webpack.plugins');

module.exports = {
  /**
   * This is the main entry point for your application, it's the first file
   * that runs in the main process.
   */
  entry: './src/main.ts',
  // Put your normal webpack config below here
  module: {
    rules: require('./webpack.rules')
  },
  plugins: plugins
};
```

Thats all that is needed to get started with Electron-Forge and React + Typescript.

**UPDATE** Many people are facing issue while importing other files. This is because of missing *extensions* configuration in webpack. In  both `webpack.renderer.config.js` and `webpack.main.config.js` include below configuration -

```
resolve: {
extensions: ['.js', '.ts', '.jsx', '.tsx', '.css']
},
```
Thanks for a lot of people in the comments below on bringing this to my attention.

