#!/bin/bash
#Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# 
#Permission is hereby granted, free of charge, to any person obtaining a copy of this
#software and associated documentation files (the "Software"), to deal in the Software
#without restriction, including without limitation the rights to use, copy, modify,
#merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
#permit persons to whom the Software is furnished to do so.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
#INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
#PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
#OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# setup graphics desktop
export DEBIAN_FRONTEND=noninteractive
export DEBCONF_NONINTERACTIVE_SEEN=true

# update and install required packages 
apt update
apt install -y git tar
apt install -y apt-transport-https ca-certificates curl gnupg-agent software-properties-common

apt install -y tzdata
apt install -y keyboard-configuration
apt install -y gnupg2
apt install -y lsb-core 
apt install -y python-minimal
apt install -y python-pip

pip install --upgrade pip
pip install awscli
pip install boto3
pip install kafka-python
pip install psycopg2-binary
pip install numpy

# install ros melodic
echo "install ros melodic ..."
sh -c 'echo "deb http://packages.ros.org/ros/ubuntu $(lsb_release -sc) main" > /etc/apt/sources.list.d/ros-latest.list' 
apt-key adv --keyserver 'hkp://keyserver.ubuntu.com:80' --recv-key C1CF6E31E6BADE8868B172B4F42ED6FBAB17C654 
apt-get update

apt install -y ros-melodic-desktop-full 
echo "source /opt/ros/melodic/setup.bash" >> /home/ubuntu/.bashrc
apt install -y python-rosdep python-rosinstall python-rosinstall-generator python-wstool build-essential
apt install -y python-rosdep

rosdep init
rosdep update

# Create roscore startup script
echo "#!/bin/bash" >> /usr/local/bin/start-roscore.sh
echo "source /opt/ros/melodic/setup.bash" >> /usr/local/bin/start-roscore.sh
echo "roscore" >> /usr/local/bin/start-roscore.sh
chmod a+x /usr/local/bin/start-roscore.sh

echo "[Unit]" >> /etc/systemd/system/roscore.service
echo "Description=roscore service" >> /etc/systemd/system/roscore.service
echo "" >> /etc/systemd/system/roscore.service
echo "[Service]" >> /etc/systemd/system/roscore.service
echo "User=ubuntu" >> /etc/systemd/system/roscore.service
echo "ExecStart=/usr/local/bin/start-roscore.sh" >> /etc/systemd/system/roscore.service
echo "Restart=on-abort" >> /etc/systemd/system/roscore.service
echo "" >> /etc/systemd/system/roscore.service
echo "[Install]" >> /etc/systemd/system/roscore.service
echo "WantedBy=graphical.target" >> /etc/systemd/system/roscore.service

systemctl enable roscore
echo "install ros melodic complete"

# install docker
echo "install Docker..."
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
apt-key fingerprint 0EBFCD88
add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
apt update
apt install -y docker-ce docker-ce-cli containerd.io
docker run hello-world
usermod -aG docker ubuntu
echo "install Docker complete"

# install DCV server
echo "install DCV server..."
apt update
apt install -y ubuntu-desktop
apt install -y lightdm
apt -y upgrade
echo "/usr/sbin/lightdm" > /etc/X11/default-display-manager
dpkg-reconfigure lightdm

apt install -y mesa-utils

nvidia-xconfig --preserve-busid --enable-all-gpus

#restart X server
echo "restart X-server"
systemctl set-default graphical.target
systemctl isolate graphical.target

wget https://d1uj6qtbmh3dt5.cloudfront.net/NICE-GPG-KEY
gpg --import NICE-GPG-KEY
wget https://d1uj6qtbmh3dt5.cloudfront.net/2020.0/Servers/nice-dcv-2020.0-8428-ubuntu1804.tgz
tar -xvzf nice-dcv-2020.0-8428-ubuntu1804.tgz
cd nice-dcv-2020.0-8428-ubuntu1804
apt install -y ./nice-dcv-server_2020.0.8428-1_amd64.ubuntu1804.deb

#restart X server
systemctl set-default graphical.target
systemctl isolate graphical.target

# Create DCV server configuration file
mkdir  /opt/dcv-session-store
echo "[license]" >> dcv.conf
echo "[log]" >> dcv.conf
echo "[session-management]" >> dcv.conf
echo "[session-management/defaults]" >> dcv.conf
echo "[session-management/automatic-console-session]" >> dcv.conf
echo "storage-root=\"/opt/dcv-session-store/\"" >> dcv.conf
echo "[display]" >> dcv.conf
echo "[connectivity]" >> dcv.conf
echo "[security]" >> dcv.conf
echo "authentication=\"system\"" >> dcv.conf
echo "[clipboard]" >> dcv.conf
echo "primary-selection-copy=true" >> dcv.conf
echo "primary-selection-paste=true" >> dcv.conf
mv dcv.conf /etc/dcv/dcv.conf

# Enable DCV server
systemctl enable dcvserver

# Create DCV session permissions files
rm -f /home/ubuntu/dcv.perms
echo "[permissions]" >> /home/ubuntu/dcv.perms
echo "%owner% allow builtin" >> /home/ubuntu/dcv.perms

# Create startup session script
echo "#!/bin/bash" >> /usr/local/bin/start-dcvsession.sh
echo "dcv create-session --type=console --owner ubuntu --storage-root /opt/dcv-session-store/ --permissions-file /home/ubuntu/dcv.perms dcvsession" >> /usr/local/bin/start-dcvsession.sh
chmod a+x /usr/local/bin/start-dcvsession.sh

echo "[Unit]" >> /etc/systemd/system/dcvsession.service
echo "Description=DCV session service" >> /etc/systemd/system/dcvsession.service
echo "After=dcvserver.service" >> /etc/systemd/system/dcvsession.service
echo "" >> /etc/systemd/system/dcvsession.service
echo "[Service]" >> /etc/systemd/system/dcvsession.service
echo "User=root" >> /etc/systemd/system/dcvsession.service
echo "ExecStart=/usr/local/bin/start-dcvsession.sh" >> /etc/systemd/system/dcvsession.service
echo "Restart= on-abort" >> /etc/systemd/system/dcvsession.service
echo "" >> /etc/systemd/system/dcvsession.service
echo "[Install]" >> /etc/systemd/system/dcvsession.service
echo "WantedBy=graphical.target" >> /etc/systemd/system/dcvsession.service

systemctl enable dcvsession
echo "install DCV server complete"

echo "install Visual Code..."
wget -q https://packages.microsoft.com/keys/microsoft.asc -O- | apt-key add -
add-apt-repository "deb [arch=amd64] https://packages.microsoft.com/repos/vscode stable main"
apt update
apt install -y code
apt autoremove -y
echo "Install Visual Code complete"

# install FSx for Lustre client
echo "install FSx for Lustre client ..."
wget -O - https://fsx-lustre-client-repo-public-keys.s3.amazonaws.com/fsx-ubuntu-public-key.asc | apt-key add -
bash -c 'echo "deb https://fsx-lustre-client-repo.s3.amazonaws.com/ubuntu bionic main" > /etc/apt/sources.list.d/fsxlustreclientrepo.list && apt-get update'
apt install -y lustre-client-modules-$(uname -r)
echo "install FSx for Lustre client complete"

# install nfs-common
apt install -y nfs-common

# install google chrome
echo "install google chrome ..."
apt remove -y firefox
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
apt install -y ./google-chrome-stable_current_amd64.deb
echo "install google chrome complete"

# install webviz
echo "setup webviz ..."

# Create startup session script
echo "#!/bin/bash" >> /usr/local/bin/start-webviz.sh
echo "docker run -p 8080:8080 cruise/webviz" >> /usr/local/bin/start-webviz.sh
chmod a+x /usr/local/bin/start-webviz.sh

echo "[Unit]" >> /etc/systemd/system/webviz.service
echo "Description=webviz service" >> /etc/systemd/system/webviz.service
echo "" >> /etc/systemd/system/webviz.service
echo "[Service]" >> /etc/systemd/system/webviz.service
echo "User=ubuntu" >> /etc/systemd/system/webviz.service
echo "ExecStart=/usr/local/bin/start-webviz.sh" >> /etc/systemd/system/webviz.service
echo "Restart=on-abort" >> /etc/systemd/system/webviz.service
echo "" >> /etc/systemd/system/webviz.service
echo "[Install]" >> /etc/systemd/system/webviz.service
echo "WantedBy=graphical.target" >> /etc/systemd/system/webviz.service

systemctl enable webviz

reboot
