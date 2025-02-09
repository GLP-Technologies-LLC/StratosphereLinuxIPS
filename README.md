<h1 align="center"> 

Slips v0.9.1


<h3 align="center"> 

[Documentation](https://stratospherelinuxips.readthedocs.io/en/develop/) — [Features](#features) — [Installation](#installation) — [Authors](#people-involved) — [Contributions](#contribute-to-slips)
</h3>

##### Repo Stars Over Time

[![Stargazers over time](https://starchart.cc/stratosphereips/StratosphereLinuxIPS.svg)](https://starchart.cc/stratosphereips/StratosphereLinuxIPS)
[![GitHub watchers](https://badgen.net/github/watchers/stratosphereips/StratosphereLinuxIPS)](https://GitHub.com/stratosphereips/StratosphereLinuxIPS/watchers/)
[![GitHub contributors](https://img.shields.io/github/contributors/stratosphereips/StratosphereLinuxIPS)](https://GitHub.com/stratosphereips/StratosphereLinuxIPS/contributors/)
[![GitHub issues](https://img.shields.io/github/issues/stratosphereips/StratosphereLinuxIPS.svg)](https://GitHub.com/stratosphereips/StratosphereLinuxIPS/issues/)
[![GitHub issues-closed](https://img.shields.io/github/issues-closed/stratosphereips/StratosphereLinuxIPS.svg)](https://GitHub.com/stratosphereips/StratosphereLinuxIPS/issues?q=is%3Aissue+is%3Aclosed)
[![GitHub open-pull-requests](https://badgen.net/github/open-prs/stratosphereips/StratosphereLinuxIPS)](https://github.com/stratosphereips/StratosphereLinuxIPS/pulls?q=is%3Aopen)
[![GitHub pull-requests closed](https://badgen.net/github/closed-prs/stratosphereips/StratosphereLinuxIPS)](https://github.com/stratosphereips/StratosphereLinuxIPS/pulls?q=is%3Aclosed)
[![GitHub version](https://badge.fury.io/gh/stratosphereips%2FStratosphereLinuxIPS.svg)](https://github.com/stratosphereips/StratosphereLinuxIPS)
![GitHub forks](https://img.shields.io/github/forks/stratosphereips/StratosphereLinuxIPS)
[![License](https://img.shields.io/badge/license-GPLv2-green)](./LICENSE)
![GitHub Org's stars](https://img.shields.io/github/stars/stratosphereips/StratosphereLinuxIPS?style=plastic)
![GitHub watchers](https://img.shields.io/github/watchers/stratosphereips/StratosphereLinuxIPS?color=green&style=plastic)
![GitHub language count](https://img.shields.io/github/languages/count/stratosphereips/StratosphereLinuxIPS)
![Docker Image Size (tag)](https://img.shields.io/docker/image-size/stratosphereips/slips/latest?color=yellow&label=docker%20image%20size)
![GitHub repo size](https://img.shields.io/github/repo-size/stratosphereips/StratosphereLinuxIPS)
![Docker Pulls](https://img.shields.io/docker/pulls/stratosphereips/slips)
![Python](https://img.shields.io/badge/Python-3.8-yellow)


[![Discord](https://img.shields.io/discord/761894295376494603?label=&logo=discord&logoColor=ffffff&color=7389D8&labelColor=6A7EC2)](https://discord.gg/zu5HwMFy5C)
[![License](https://img.shields.io/badge/Blog-Stratosphere-red)](https://www.stratosphereips.org/blog/tag/slips)
[![Docker](https://img.shields.io/badge/Docker-latest-success)](https://hub.docker.com/r/stratosphereips/slips_p2p)
![Twitter Follow](https://img.shields.io/twitter/follow/StratosphereIPS?style=social)
<hr>

<h1>
Behavioral Machine Learning Based Intrusion Prevention System
</h1>

Slips is a behavioral intrusion prevention system that uses machine learning to detect malicious behaviors in the
network traffic. Slips is designed to focus on targeted attacks, detection of command and control channels, and to
provide a good visualisation for the analyst. It can analyze network traffic in real time, network captures such as pcap
files, and network flows produced by Suricata, Zeek/Bro and Argus. Slips processes the input, analyzes it, and
highlights suspicious behaviour that need the analyst attention.

<img src="https://raw.githubusercontent.com/stratosphereips/StratosphereLinuxIPS/develop/docs/images/slips.gif" width="850px"
title="Slips in action.">



# Features

Slips is written in Python and is highly modular. Each module is designed to perform a specific detection in the network traffic. The complete documentation of Slips internal architecture and instructions how to implement a new module are available [here](https://stratospherelinuxips.readthedocs.io/en/develop/).

The following table summarizes all active modules in Slips, its status and purpose:

|   Module            | Status | Description | 
| --------------------|   :-:  |------------ |  
| https               |   ⏳   | training and testing of the Random Forest algorithm to detect malicious HTTPS flows |
| port scan detector  |   ✅   | detects horizontal and vertical port scans |
| rnn-cc-detection    |   ✅   | detects command and control channels using recurrent neural network and the Stratosphere behavioral letters |
| flowalerts          |   ✅   | detects a malicious behaviour in each flow. Current measures are: long duration of the connection, successful ssh |
| flowmldetection     |   ✅   | detects malicious flows using ML pretrained models |
| leak_detector       |   ✅   | detects leaks of data in the traffic using YARA rules |
| threat Intelligence |   ✅   | checks IPs against known threat intelligence lists |
| ARP                 |   ✅   | checks for ARP attacks in ARP traffic  |
| timeline            |   ✅   | creates a timeline of what happened in the network based on all the flows and type of data available  |
| VirusTotal          |   ✅   | lookups IP addresses on VirusTotal |
| RiskIQ              |   ✅   | lookups IP addresses on RiskIQ  |
| IP_Info             |   ✅   | lookups Geolocation, ASN, RDNS information from IPs and MAC vendors |
| CESNET              |   ✅   | sends and receives alerts from CESNET Warden servers |
| ExportingAlerts     |   ✅   | exports alerts to Slack, STIX or Suricata-like JSON format |
| http_analyzer       |   ✅   | analyzes HTTP traffic |
| blocking            |   ✅   | blocks malicious IPs connecting to the device |
| P2P                 |   ✅   | shares network detections with other Slips peers in the local network |
| Kalipso             |   ✅   | Slips console graphical user interface to show detection with graphs and tables |

# Installation

There are two ways to run Slips: i. bare metal installation on Linux, or ii. using Docker which is our preferred option. In this section we guide you through how to get started with Slips.

## Running Slips Using Docker

The easiest way to run Slips is using Docker. The latest Slips docker image can analyze multiple type of network data, including pcaps, Zeek flows, Argus flows, and others. In Linux systems, it is possible to use the docker image to analyze traffic in real time from the host interface.

### Getting started with Slips docker

Get started with Slips in three simple steps: i. create a new container from the latest Slips docker image, ii. access the container, and iii. run Slips on a sample pcap to test things work as expected. Below you can find the step by step guide on how to proceed.

First, download the latest docker image and spawn a Slips container in daemon mode:

        docker run -it -d --rm --name slips stratosphereips/slips:latest
        
Second, get a terminal on the newly created container so we can run Slips:

        docker exec -it slips /bin/bash

Third, run Slips inside the container. The parameter `-c` specifies the Slips configuration to use, and the parameter `-f` specifies the input file to analyze:

        ./slips.py -c slips.conf -f dataset/hide-and-seek-short.pcap
        
Slips will first update the Threat Intelligence (TI) feeds, this process may take some minutes. Once the TI feeds are updated, Slips will proceed with analyzing the given file. When the analysis finishes, the results will be stored in the `output/alerts.log` file.

### Run Slips sharing files between the host and the container

The following instructions will guide you on how to run a Slips docker container with file sharing between the host and the container.

```bash
    # create a directory to load pcaps in your host computer
    mkdir ~/dataset
    
    # copy the pcap to analyze to the newly created folder
    cp <some-place>/myfile.pcap ~/dataset
    
    # create a new Slips container mapping the folder in the host to a folder in the container
    docker run -it --rm --net=host --name slips -v $(pwd)/dataset:/StratosphereLinuxIPS/dataset stratosphereips/slips:latest
    
    # run slips on the pcap file mapped to the container
    ./slips.py -c slips.conf -f dataset/myfile.pcap
```

### Run Slips with access to block traffic on the host network

To allow the Slips docker container to analyze and block the traffic in your Linux host network interface, it is necessary to run the docker container with the option `--cap-add=NET_ADMIN`. This option allows the container to interact with the network stack of the host computer. To allow blocking malicious behavior, run Slips with the parameter `-p`.

```bash
    # run a new Slips container with the option to interact with the network stack of the host
    docker run -it --rm --net=host --cap-add=NET_ADMIN --name slips stratosphereips/slips:latest
    
    # run slips on the host interface `eno1` with active blocking `-p`
    ./slips.py -c slips.conf -i eno1 -p
```
### Build Slips from the Dockerfile

To build a local docker image of Slips follow the next steps:

```bash
    # clone the Slips repository in your host computer
    git clone https://github.com/stratosphereips/StratosphereLinuxIPS.git
    
    # access the Slips repository directory
    cd StratosphereLinuxIPS/
    
    # build the docker image from the recommended Dockerfile
    docker build --no-cache -t slips -f docker/ubuntu-image/Dockerfile .
    
    # run a new Slips container from the freshly built local image
    docker run -it --rm --net=host --name slips slips
    
    # run Slips using the default configuration in one of the provided test datasets
    ./slips.py -c slips.conf -f dataset/test3.binetflow
```

## Slips Bare Metal Installation

To install Slips in your host computer there are three core things needed: i. installing Python dependencies, ii. installing Redis, and iii. installing `zeek` (formerly `bro`) for pcap analysis. 

### Clone Slips repository

The first step is to clone the Slips repository to your host computer:

```bash
    # clone repository
    git clone https://github.com/stratosphereips/StratosphereLinuxIPS.git
    
    # access the Slips directory
    cd StratosphereLinuxIPS
```

### Installing Redis

Slips needs Redis for interprocess communication. Redis can be installed directly in the host computer or can be run using Docker.

To run Redis directly on the host run:

        redis-server --daemonize yes
    
To run a Redis docker container run:

        docker run --rm -d --name slips_redis -p 6379:6379 redis:alpine

### Installing Python dependencies

We recommend using [Conda](https://docs.conda.io/en/latest/) for the Python environment management:

```bash
    # create conda environment and download all Python dependencies
    conda env create -f conda-environment.yaml
    
    # activate the conda environment
    conda activate slips 
```

### Installing Zeek for pcap analysis

Additionally, you may need to install either `zeek` or `bro` in order to have the capability to analyze pcap files. Follow the official installation guide from [Zeek Website](https://zeek.org/get-zeek/). Check [slips.py](slips.py) and its usage on the `check_zeek_or_bro` function.

### Run Slips

After all dependencies are installed and Redis is running, you are ready to run Slips. Copy pcap files or other flow files in the ./dataset/ folder and analyze them:

```bash
    # run Slips with the default configuration
    # use a sample pcap of your own
    ./slips.py -c slips.conf -f dataset/myfile.pcap
```

## P2P Module
The peer to peer system os Slips is a highly complex automatic system to find other peers in the network and share data on IoC automatically in a balanced, trusted way. You just have to enable the P2P system. Please check the documentation [here](../docs/P2P.md)

You can use Slips with P2P directly in a special docker image by doing:

```bash
    # download the Slips P2P docker image
    docker pull stratosphereips/slips_p2p
    
    # run Slips on the local network
    docker run --name slipsp2p -d -it --rm --net=host --cap-add=NET_ADMIN stratosphereips/slips_p2p
```

# Train The Machine Learning Models With Your Data

Slips' machine learning models can be extended by running Slips in _training_ mode with the user network traffic, leading to a improvement in the detection.

To use this feature you need to modify the configuration file ```slips.conf``` to add in the ```[flowmldetection]``` section:

        mode = train

The machine learning model needs a label for this new traffic to know what type of traffic will it learn from. Add the following label:

        label = normal

Run Slips normally in your data, interface or any input file, and the machine learning model will be updated automatically.

To use the new model, reconfigure Slips to run in `test` mode by updating the ```slips.conf``` file with:

        mode = train
    
# Slips in the Media

- 2021 BlackHat Europe Arsenal, Slips: A Machine-Learning Based, Free-Software, Network Intrusion Prevention System [[slides](https://mega.nz/file/EAIjWA5D#DoYhJknH1hpbqfS2ayVLwA7ewNT50jFQb7S3dVAKPko)] [[web](https://www.blackhat.com/eu-21/arsenal/schedule/#slips-a-machine-learning-based-free-software-network-intrusion-prevention-system-25116)]
- 2021 BlackHat USA Arsenal, Slips: A Machine-Learning Based, Free-Software, Network Intrusion Prevention System [[web](https://www.blackhat.com/us-21/arsenal/schedule/#slips-a-machine-learning-based-free-software-network-intrusion-prevention-system-24105)]
- 2021 BlackHat Asia Arsenal, Slips: A Machine-Learning Based, Free-Software, Network Intrusion Prevention System [[web](https://www.blackhat.com/asia-21/arsenal/schedule/#slips-a-machine-learning-based-free-software-network-intrusion-prevention-system-22576)]
- 2020 Hack In The Box CyberWeek, Android RATs Detection With A Machine Learning-Based Python IDS [[video](https://www.youtube.com/watch?v=wx0V3qWdmyk)]
- 2019 OpenAlt, Fantastic Attacks and How Kalipso can Find Them [[video](https://www.youtube.com/watch?v=p2FL2sECpS0&t=1s)]
- 2016 Ekoparty, Stratosphere IPS. The free machine learning malware detection [[video](https://www.youtube.com/watch?v=IazEdK8R4YI)]

# People Involved

**Founder:** Sebastian Garcia, sebastian.garcia@agents.fel.cvut.cz, eldraco@gmail.com. 

**Main authors:** Sebastian Garcia, Alya Gomaa, Kamila Babayeva

**Contributors:**
- Veronica Valeros
- Frantisek Strasak
- Dita Hollmannova
- Ondrej Lukas
- Elaheh Biglar Beigi
- Maria Rigaki 
- kartik88363
- arkamar

# Contribute to Slips
All contributors are welcomed! How you can help?

- Read our [contributing](.github/CONTRIBUTING.md) guidelines.
- Run Slips and report bugs, make feature requests, and suggest ideas.
- Open a pull request with a solved GitHub issue and new feature.
- Open a pull request with a new detection module. The instructions and a template for new detection module [here](https://stratospherelinuxips.readthedocs.io/en/develop/).
- Join our community at [Discord](https://discord.gg/zu5HwMFy5C), ask questions, suggest new features or give us feedback.


# Acknowledgments

Slips was funded by the following organizations.

- NlNet Foundation, https://nlnet.nl/
- AIC Group, Czech Technical University in Prague, https://www.aic.fel.cvut.cz/
- Avast Software, https://www.avast.com/
- CESNET, https://www.cesnet.cz/
