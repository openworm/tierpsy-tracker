
# Installing from source 
## **Apple macOS**

### 1. **Download and Install Anaconda**

Open a terminal window and check if you have conda by typing:
```bash
conda --version
```
If conda is not installed follow this:

Download **Anaconda version 23.3.1 or higher** from [this link](https://repo.anaconda.com/archive). 

**Note:** Conda 25.3.1 and 24.11.3 have also been tested successfully.
  - File: `Anaconda3-2023.03-1-MacOSX-arm64.sh`

Download the .sh file and change directory in terminal to where the file's been downloaded. Then use this command:
```bash
bash Anaconda3-2023.03-1-MacOSX-arm64.sh 
```
If encountered error regarding "conda init" at final stage of Anaconda installation, it can be fixed manually by the command below after replacing '[username]' with your own username:
```bash
/Users/[username]/anaconda3/bin/conda init zsh
source ~/.zshrc
```
Finally, validate the conda installation:
```bash
conda --version
```

---

### 2. **Tierpsy Installation**

#### 2.1. Clone Tierpsy Tracker Repository
Open a terminal and run the following commands to clone the Tierpsy repository:

```bash
git clone https://github.com/Tierpsy/tierpsy-tracker.git
cd tierpsy-tracker
```

#### 2.2. Create a Conda Environment

Create an environement:
```bash
conda create -n tierpsy python=3.8 
```
Activate the new environment by:
```bash
conda activate tierpsy
```

#### 2.3. Install Dependencies

This step might take a while. Install dependencies using:

```bash
conda install --file requirements-macos.txt
pip install imgstore
```

#### 2.4. Install Tierpsy
gcc version 11 is required for this step. You can check if you have gcc version 11 or not with "gcc-11 --version" in the command-line. if you got a 'command not found: gcc-11', it's not installed skip here and check part "3. Installing GCC".

```bash
CC=gcc-11 pip install -e .
```
### 3. Installing GCC
#### 3.1. Install Homebrew
Check if you have homebrew, type:

```bash
which brew
```
If it returns a path, Homebrew is already installed and continue from step 3.2.
If you don't have Homebrew installed, install it by running this command in the terminal:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

To verify that Homebrew is installed, type:

```bash
which brew
```
You might need to run suggested displayed commands under the section "Next Steps" in the terminal window to add Homebrew to path.  
Alternatively, you can run the commands below in your terminal after replacing [username] with your username to add Homebrew to your PATH:
```bash
echo >> /Users/[username]/.zprofile

echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >› /Users/[username]/.zprofile

eval "$(/opt/homebrew/bin/brew shellenv)"
```

To verify that Homebrew is installed, type:

```bash 
which brew
```

If it returns a path, Homebrew is installed correctly.

#### 3.2. Install gcc
Next, install gcc 11:

```bash
brew install gcc@11 
```

#### 3.3. Install Tierpsy 
```bash
CC=gcc-11 pip install -e .
```

#### 4. Run Tierpsy
Activate environment if it's not already activated and run tierpsy_gui
```bash
conda activate tierpsy
tierpsy_gui
```

---

With these steps, Tierpsy should be successfully installed on Apple Silicon Macs.

## Installation from source for Windows and Linux

> This is the preferred installation method if you want to have constant updates and/or contribute to Tierpsy's development.

- Download Python >= 3.6 using [anaconda](https://www.anaconda.com/download/) or [miniconda](https://conda.io/miniconda.html).
- Install [git](https://git-scm.com/). [Here](https://gist.github.com/derhuerst/1b15ff4652a867391f03) are some instructions to install it. [GitHub Desktop](https://desktop.github.com/) is also an option if you prefer a graphical interface.
- Install a [C compiler compatible with cython](http://cython.readthedocs.io/en/latest/src/quickstart/install.html). In Windows, you can use [Visual C++ 2015 Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/). In OSX, we recommend to download XCode from the AppStore.
- Follow the OS-specific instructions below.

### Windows 10
- Clone the repository in a folder named `tierpsy-tracker`. You can do this either:
    - via a git prompt
    - with your browser: `Clone or Download` -> `Download ZIP`, then unzip and rename the folder
    - with your browser: `Clone or Download` -> `Open in Desktop`, then continue with [GitHub Desktop](https://desktop.github.com/)
- Open the Anaconda prompt, move to the `tierpsy-tracker` folder using the `cd` command appropriately, and type:
```bash
conda env create -f tierpsy_windows.yml #[Windows 10]
conda activate tierpsy
pip install -e .
tierpsy_gui
```

#### Troubleshooting
- Make sure you have an up-to-date version of conda. To update conda, `conda update -n base -c defaults conda`. We tested on `conda 4.8.2`.
- Try the alternative command `conda env create -f tierpsy_windows_conda4_5_11.yml`
- `pip install -e .` has been known to fail with an error stating that `command 'cl.exe' failed: No such file or directory`. See the [Known Issues](ISSUES.md) for a solution.
- Windows machines without a CUDA enabled GPU: see the [Known Issues](ISSUES.md).

### Linux
- Open a shell and type:
```bash
git clone https://github.com/Tierpsy/tierpsy-tracker
cd tierpsy-tracker
conda create -n tierpsy #[optional]
conda activate tierpsy #[optional]
conda install --file requirements.txt
pip install -e .
tierpsy_gui
```
