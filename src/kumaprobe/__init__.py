import docker
import asyncio
import aiohttp
import uvloop
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

client = docker.DockerClient(base_url="unix://var/run/docker.sock")


async def send_health_status(endpoint, status):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(endpoint, json={"status": status}) as response:
                if response.status == 200:
                    logger.info(f"Successfully sent health status to {endpoint}")
                else:
                    logger.warning(
                        f"Received unexpected response {response.status} from {endpoint}"
                    )
        except Exception as e:
            logger.error(f"Failed to send health status to {endpoint}: {e}")


async def check_health_and_send(container_or_service):
    labels = container_or_service.attrs.get("Config", {}).get("Labels", {})

    if "health" in labels and "kumaprobe.endpoint" in labels:
        health_status = container_or_service.attrs["State"]["Health"]["Status"]
        endpoint = labels["kumaprobe.endpoint"]

        if health_status == "healthy":
            await send_health_status(endpoint, health_status)
        else:
            logger.warning(
                f"{container_or_service.name} is not healthy: {health_status}"
            )


async def check_active_containers():
    containers = client.containers.list()
    return containers


async def check_active_services():
    services = client.services.list()
    return services


async def check_swarm_mode():
    try:
        client.swarm.attrs
        logger.info("Swarm mode is active.")
        return True
    except docker.errors.APIError:
        logger.info("Swarm mode is inactive or unavailable.")
        return False
    except Exception as e:
        logger.error(f"Error checking Swarm mode: {e}")
        return False


async def async_main():
    detected_services = set()
    detected_containers = set()

    logger.info("Checking if Swarm mode is active.")
    is_swarm_active = await check_swarm_mode()

    if is_swarm_active:
        logger.info("Checking services in Swarm mode.")
        services = await check_active_services()

        for service in services:
            labels = service.attrs.get("Spec", {}).get("Labels", {})
            if any(label.startswith("kumaprobe") for label in labels):
                detected_services.add(service.id)
                logger.info(f"Detected service with kumaprobe label: {service.name}")

    containers = await check_active_containers()
    for container in containers:
        labels = container.attrs.get("Config", {}).get("Labels", {})
        if any(label.startswith("kumaprobe") for label in labels):
            if container.id not in detected_services:
                detected_containers.add(container.id)
                logger.info(f"Detected container with kumaprobe label: {container.name}")

    while True:
        current_containers = await check_active_containers()
        for container in current_containers:
            labels = container.attrs.get("Config", {}).get("Labels", {})
            if any(label.startswith("kumaprobe") for label in labels):
                if container.id not in detected_containers and container.id not in detected_services:
                    detected_containers.add(container.id)
                    logger.info(f"New container detected with kumaprobe label: {container.name}")

        for container in current_containers:
            await check_health_and_send(container)

        await asyncio.sleep(60)


def main():
    uvloop.install()
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
