import os
import shutil
import sys
import time

from azure.storage.blob import BlobServiceClient, BlobLeaseClient
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError


class VmScript:
    def __init__(self, storage1_connection_string, storage2_connection_string):
        self.storage1_connection_string = storage1_connection_string
        self.storage2_connection_string = storage2_connection_string
        self.blobs_local_folder = 'Blobs'
        self.container_name = 'df-container-1'
        self.blob_service_client1 = BlobServiceClient.from_connection_string(self.storage1_connection_string)
        self.blob_service_client2 = BlobServiceClient.from_connection_string(self.storage2_connection_string)

    def create_local_blobs(self, blob_num):       
        if os.path.exists(self.blobs_local_folder):
            shutil.rmtree(self.blobs_local_folder)
        os.makedirs(self.blobs_local_folder)
        for i in range(1, blob_num+1):
            file_name = ('blob_{}.txt'.format(str(i).zfill(3)))
            with open(os.path.join(self.blobs_local_folder, file_name), 'w') as f:
                f.write('Filename: {}'.format(file_name))

    def clear_storages(self):
        container_client1 = self.blob_service_client1.get_container_client(container=self.container_name)
        try:
            container_client1.delete_container()
        except ResourceNotFoundError:
            print('Container {} does not exist'.format(self.container_name))
        container_client2 = self.blob_service_client2.get_container_client(container=self.container_name)
        try:
            container_client2.delete_container()
        except ResourceNotFoundError:
            print('Container {} does not exist'.format(self.container_name))

        # TODO: need to find a smarter way to check whether containers were deleted completely
        print("Sleeping 40 s to ensure containers were deleted completely...")
        time.sleep(40)

        

    def upload_blobs_to_storage1(self):
        # Create container on storage 1:
        self.blob_service_client1.create_container(self.container_name, public_access='container')
        local_blobs_file_list = os.listdir(self.blobs_local_folder)
        for file in local_blobs_file_list:
            blob_client = self.blob_service_client1.get_blob_client(container=self.container_name, blob=file)
            with open(os.path.join(self.blobs_local_folder, file), 'rb') as f:
                print("Uploading {}".format(file))
                blob_client.upload_blob(f)
                

    def copy_blobs_from_storage1_to_storage2(self):
        container_client1 = self.blob_service_client1.get_container_client(container=self.container_name)
        blob_list = container_client1.list_blobs()
        
        # Create container on storage account 2
        try:
            self.blob_service_client2.create_container(self.container_name)
        except ResourceExistsError:
            print("Container name {} already exists in storage account 2".format(self.container_name))
        for source_blob_properties in blob_list:
            source_blob = self.blob_service_client1.get_blob_client(container=self.container_name, blob=source_blob_properties.name)
            # Lease the source blob during copy to prevent other clients from modifying it

            lease = BlobLeaseClient(client=source_blob)

            # Create an infinite lease by passing -1
            # We'll break the lease after the copy operation finishes
            lease.acquire(-1)
            destination_blob = self.blob_service_client2.get_blob_client(container=self.container_name, blob=source_blob_properties.name)
            destination_blob.start_copy_from_url(source_url=source_blob.url)
            # Get the destination blob properties
            destination_blob_properties = destination_blob.get_blob_properties()
            print(f"Copying {source_blob_properties.name}")
            print(f"Copy status: {destination_blob_properties.copy.status}")
            print(f"Copy progress: {destination_blob_properties.copy.progress}")
            print(f"Copy completion time: {destination_blob_properties.copy.completion_time}")
            print(f"Total bytes copied: {destination_blob_properties.size}")

            # Break the lease on the source blob
            if source_blob_properties.lease.state == "leased":
                lease.break_lease()
                # Display updated lease state
                print(f"Source blob lease state: {source_blob_properties.lease.state}")


if __name__ == "__main__":
    storage1_connection_string = str(sys.argv[1])
    storage2_connection_string = str(sys.argv[2])
    script = VmScript(storage1_connection_string, storage2_connection_string)
    script.create_local_blobs(100)
    script.clear_storages()
    script.upload_blobs_to_storage1()
    script.copy_blobs_from_storage1_to_storage2()


