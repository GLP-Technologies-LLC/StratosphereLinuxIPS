# Installation

There are two ways to install and run Slips: inside a Docker or in your own computer. We suggest to install and to run Slips inside a Docker since all dependencies are already installed in there. However, current version of docker with Slips does not allow to capture the traffic from the computer's interface. We will describe both ways of installation anyway. 

## Linux

### Installing and running Slips inside a Docker.

Slips can be run inside a Docker. There is a prepared docker image with Slips available in DockerHub and it is also possible to build a docker with Slips locally from the Dockerfile. But in both cases, you have to have the Docker platform installed in your computer. Instructions how to install Docker is https://docs.docker.com/get-docker/. 

#### Running Slips inside a Docker from the DockerHub

	mkdir ~/dataset
	cp <some-place>/myfile.pcap ~/dataset
	docker run -it --rm --net=host -v ~/dataset:/StratosphereLinuxIPS/dataset stratosphereips/slips:latest
	./slips.py -c slips.conf -r dataset/myfile.pcap

#### Building the docker with Slips from the Dockerfile

Before building the docker locally from the Dockerfile, first you should clone Slips repo or download the code directly: 

	git clone https://github.com/stratosphereips/StratosphereLinuxIPS.git

If you cloned Slips in '~/code/StratosphereLinuxIPS', then you can build the Docker image with:

	cd ~/code/StratosphereLinuxIPS/docker
	docker build --no-cache -t slips -f Dockerfile .
	docker run -it --rm --net=host -v ~/code/StratosphereLinuxIPS/dataset:/StratosphereLinuxIPS/dataset slips
	./slips.py -c slips.conf -f dataset/test3.binetflow

If you don't have Internet connection from inside your Docker image while building, you may have another set of networks defined in your Docker. For that try:

	docker build --network=host --no-cache -t slips -f Dockerfile .
	
You can also put your own files in the /dataset/ folder and analyze them with Slips:

	cp some-pcap-file.pcap ~/code/StratosphereLinuxIPS/dataset
	docker run -it --rm --net=host -v ../dataset/:/StratosphereLinuxIPS/dataset slips
	./slips.py -c slips.conf -f dataset/some-pcap-file.pcap


### Install in Linux (Ubuntu, Debian was tested)

First you can try to install using install.sh

	sudo chmod +x install.sh
	sudo ./install.sh
	
or install every package manually

#### Installing Python, Redis, NodeJs, and required python and npm libraries.
Update the repository of packages so you see the latest versions:

	apt-get update
	
Install the required packages (-y to install without asking for approval):

    apt-get -y install tshark iproute2 python3-tzlocal net-tools python3-dev build-essential python3-certifi curl git gnupg ca-certificates redis wget python3-minimal python3-redis python3-pip python3-watchdog nodejs redis-server npm lsof file iptables nfdump zeek
	
Even though we just installed pip3, the package installer for Python (3.7), we need to upgrade it to its latest version:

	python3 -m pip install --upgrade pip

Now that pip3 is upgraded, we can proceed to install all required packages via pip3 python packet manager:

	sudo pip3 install -r requirements.txt

_Note: for those using a different base image, you need to also install tensorflow==2.2.0 via pip3._

As we mentioned before, the GUI of Slips known as Kalipso relies on NodeJs. Make sure to use NodeJs greater than version 12. For Kalipso to work, we will install the following npm packages:

	npm install blessed blessed-contrib redis async chalk strip-ansi@6.0.0 clipboardy fs sorted-array-async yargs

####  Installing Zeek

The last requirement to run Slips is Zeek. Zeek is not directly available on Ubuntu or Debian. To install it, we will first add the repository source to our apt package manager source list. The following two commands are for Ubuntu, check the repositories for the correct version if you are using a different OS:

	echo 'deb http://download.opensuse.org/repositories/security:/zeek/xUbuntu_18.04/ /' | tee /etc/apt/sources.list.d/security:zeek.list

We will download and store the gpg signature from the package for apt to read:

	curl -fsSL http://download.opensuse.org/repositories/security:/zeek/xUbuntu_18.04/Release.key | gpg --dearmor | tee /etc/apt/trusted.gpg.d/security_zeek.gpg > /dev/null

Finally, we will update the package manager repositories and install zeek

	apt-get update
	apt-get -y install zeek
	
To make sure that zeek can be found in the system we will add its link to a known path:

	ln -s /opt/zeek/bin/zeek /usr/local/bin

#### Running Slips for the First Time

When running Slips for the first time we need to start Redis:

	redis-server --daemonize yes

Once Redis is running it’s time to clone the Slips repository and run it:

	git clone https://github.com/stratosphereips/StratosphereLinuxIPS.git
	cd StratosphereLinuxIPS/
	./slips.py -c slips.conf -r datasets/hide-and-seek-short.pcap

Run slips with sudo to enable blocking (Optional) 


## Install Slips on a Raspberry PI

Slips should be installed just as in a Linux native system, but instead of compiling zeek, you need to grab the zeek binaries for ARM.

Packages for Raspbian 11:
[https://download.opensuse.org/repositories/security:/zeek/Raspbian_11/armhf/zeek_4.2.0-0_armhf.deb](https://download.opensuse.org/repositories/security:/zeek/Raspbian_11/armhf/zeek_4.2.0-0_armhf.deb)

Packages for Raspbian 10:
[https://download.opensuse.org/repositories/security:/zeek/Raspbian_10/armhf/zeek_4.2.0-0_armhf.deb](https://download.opensuse.org/repositories/security:/zeek/Raspbian_10/armhf/zeek_4.2.0-0_armhf.deb)




## Install Slips on Macos
Until April 2nd 2022, macos M1 has some problems with threading modules and watchers. This is stopping Slips from running natively so far (was running until some months ago). So the best way to run locally in macos M1 is using Docker.

#### Docker in macos for pcaps, files, zeek folders, etc. But **not** capturing traffic from the host interface.
If you don't want to capture traffic from your host interface, then you can just run this image directly:

xxxxxxxxxxxxxxx

#### Docker in macos for capturing traffic in the host interface
If you want Slips to analyze the traffic in your host interface, then you need to do a horrible trick for now. This is because up to April 2nd 2022, Docker **does not support containers accessing the host interface directly**.

1. First  to do this you need to run the macos Docker image, but sharing a volume folder between your host and container

xxxxxxxxxxxxxxxx

		docker exec slips-macos redis-server --daemonize yes
		docker exec -it slips-macos /bin/bash
		cd StratosphereLinuxIPS/
		./slips.py -c slips.conf -f zeek_files


2. Second, you need to run *in your host* a zeek command, reading packets from your interface and storing the files in the shared volume

		cd zeek_files
		zeek -i en0 -C tcp_inactivity_timeout=3600mins tcp_attempt_delay=1min ../zeek-scripts/


### Macos
Until April 2nd 2022, macos M1 has some problems with threading modules and watchers. So the best way to run locally in macos M1 is for now using Docker.

#### Docker in macos for pcaps, files, zeek folders, etc. But **not** capturing traffic from the host interface.


#### Docker in macos for capturing traffic in the host interface
The problem is that Docker for macos M1 does not support yet
zeek -i en0 -C tcp_inactivity_timeout=3600mins tcp_attempt_delay=1min ../zeek-scripts/

