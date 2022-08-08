# Setting up docker for casm

https://docs.docker.com/network/bridge/

docker network create casm_docker

daemon.json

{
  "bip": "192.168.1.5/24",
  "fixed-cidr": "192.168.1.5/25",
  "fixed-cidr-v6": "2001:db8::/64",
  "mtu": 1500,
  "default-gateway": "10.20.1.1",
  "default-gateway-v6": "2001:db8:abcd::89",
  "dns": ["10.20.1.2","10.20.1.3"]
}

docker run -P --network casm_docker --hostname casm_ --mount type=bind,source=c:/Users/Andres,target=/app --rm -it -v `pwd`:/root/ casmcode/casm bash

two options for mounting:
--mount type=bind,source=c:/Users/Andres,target=/app

or:

-v c:/Users/Andres:/root/
-v c:\Users\Andres\source\repos:/shared

-----------------------------------------
Inside Docker Container
-----------------------------------------
tclient = TincClient("host.docker.internal")
db = DiskBufferJson("out.json","rel_path","/shared")
tclient.register_disk_buffer(db)