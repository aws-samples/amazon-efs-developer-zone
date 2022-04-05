create table
a2d2.drive_data
(
vehicle_id varchar(255) encode Text255 not NULL,
scene_id varchar(255) encode Text255 not NULL,
sensor_id varchar(255) encode Text255 not NULL,
data_ts BIGINT not NULL sortkey,
s3_bucket VARCHAR(255) encode lzo NOT NULL,
s3_key varchar(255) encode lzo NOT NULL,
primary key(vehicle_id, scene_id),
FOREIGN KEY(vehicle_id) references a2d2.vehicle(vehicleid),
FOREIGN KEY(sensor_id) references a2d2.sensor(sensorid)
)
DISTSTYLE AUTO
;