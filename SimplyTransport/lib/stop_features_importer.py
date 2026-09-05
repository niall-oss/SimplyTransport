from datetime import datetime

import rich.progress as rp
from geojson import FeatureCollection
from sqlalchemy import delete, select

from ..domain.stop.stop_model import StopModel
from ..domain.stop_features.stop_feature_model import StopFeatureModel
from .db.database import async_session_factory

progress_columns = (
    rp.SpinnerColumn(finished_text="✅"),
    "[progress.description]{task.description}",
    rp.BarColumn(),
    rp.MofNCompleteColumn(),
    rp.TaskProgressColumn(),
    "|| Taken:",
    rp.TimeElapsedColumn(),
    "|| Left:",
    rp.TimeRemainingColumn(),
)


class StopFeaturesImporter:
    def __init__(
        self,
        dataset: str,
        stops: FeatureCollection,
        poles: FeatureCollection,
        shelters: FeatureCollection,
        rtpis: FeatureCollection,
    ):
        self.dataset = dataset
        self.stops = stops
        self.poles = poles
        self.shelters = shelters
        self.rtpis = rtpis

    async def clear_database(self):
        """Clears the table in the database that corresponds to the dataset"""

        with rp.Progress(*progress_columns) as progress:
            task = progress.add_task("[green]Clearing database...", total=1)
            async with async_session_factory() as session:
                delete_stopfeatures = delete(StopFeatureModel).where(StopFeatureModel.dataset == self.dataset)
                await session.execute(delete_stopfeatures)
                await session.commit()
                progress.update(task, advance=1)

    async def import_stop_features(self) -> dict:
        """Imports stop features from the given dataset"""

        total_stop_features = len(self.stops["features"])

        with rp.Progress(*progress_columns) as progress:
            task = progress.add_task("[green]Importing Stop Features...", total=total_stop_features)

            objects_to_commit = []
            async with async_session_factory() as session:
                result_stops = await session.execute(
                    select(StopModel.id).filter(StopModel.dataset == self.dataset).distinct()
                )
                existing_stops = set(result_stops.scalars())

                # Create dictionaries for faster lookup
                rtpi_dict = {rtpi["properties"]["AtcoCode"]: rtpi for rtpi in self.rtpis["features"]}
                shelter_dict = {
                    shelter["properties"]["AtcoCode"]: shelter for shelter in self.shelters["features"]
                }
                pole_dict = {pole["properties"]["AtcoCode"]: pole for pole in self.poles["features"]}

                for stop in self.stops["features"]:
                    if stop["properties"]["AtcoCode"] == "":
                        progress.update(task, advance=1)
                        continue

                    if stop["properties"]["AtcoCode"] not in existing_stops:
                        progress.update(task, advance=1)
                        continue

                    survey_parsed_to_bool = stop["properties"]["IsSurveyed"] != "0"

                    stop_feature = StopFeatureModel(
                        stop_id=stop["properties"]["AtcoCode"],
                        stop_name_ie=stop["properties"]["SCN_Gaeilge"],
                        stop_type=stop["properties"]["StopType"],
                        bearing=stop["properties"]["Bearing"],
                        nptg_locality_ref=stop["properties"]["NptgLocalityRef"],
                        bays=(
                            int(stop["properties"]["PtBayCount"])
                            if stop["properties"]["PtBayCount"]
                            else None
                        ),
                        standing_area=stop["properties"]["StandingArea"],
                        bike_stand=stop["properties"]["BikeStand"],
                        bench=stop["properties"]["Bench"],
                        bin=stop["properties"]["Bin"],
                        stop_accessability=stop["properties"]["StopAccessibility"],
                        wheelchair_accessability=stop["properties"]["WheelchairAccessibility"],
                        castle_kerbing=stop["properties"]["CastleKerbing"],
                        footpath_to_stop=stop["properties"]["FootpathToStop"],
                        step_at_stop=stop["properties"]["StepAtStop"],
                        bike_lane_front=stop["properties"]["BikeLaneFront"],
                        bike_lane_rear=stop["properties"]["BikeLaneRear"],
                        surveyed=survey_parsed_to_bool,
                        ud_surveyor=stop["properties"]["UD_Surveyor"],
                        ud_calculated=stop["properties"]["UD_Calculated"],
                        rtpi_active=False,
                        shelter_active=False,
                        pole_active=False,
                        dataset=self.dataset,
                    )

                    rtpi = rtpi_dict.get(stop_feature.stop_id)
                    if rtpi:
                        stop_feature.rtpi_active = True
                        stop_feature.lines = rtpi["properties"]["Name"]
                        stop_feature.integrated_into_shelter = rtpi["properties"]["IntegratedIntoShelter"]
                        stop_feature.last_updated_rtpi = datetime.strptime(
                            rtpi["properties"]["LastUpdatedDateUtc"][:-1], "%Y-%m-%d %H:%M:%S.%f"
                        )

                    shelter = shelter_dict.get(stop_feature.stop_id)
                    if shelter:
                        stop_feature.shelter_active = True
                        stop_feature.shelter_description = shelter["properties"]["Description"]
                        stop_feature.shelter_type = (
                            int(shelter["properties"]["ShelterTypeId"])
                            if shelter["properties"]["ShelterTypeId"]
                            else None
                        )
                        stop_feature.power = shelter["properties"]["Power"]
                        stop_feature.light = shelter["properties"]["Light"]
                        stop_feature.last_updated_shelter = datetime.strptime(
                            shelter["properties"]["LastUpdatedDateUtc"][:-1],
                            "%Y-%m-%d %H:%M:%S.%f",
                        )

                    pole = pole_dict.get(stop_feature.stop_id)
                    if pole:
                        stop_feature.pole_active = True
                        stop_feature.position = pole["properties"]["Position"]
                        stop_feature.socket_type = pole["properties"]["SocketType"]
                        stop_feature.pole_type = pole["properties"]["PoleType"]
                        stop_feature.last_updated_pole = datetime.strptime(
                            pole["properties"]["LastUpdatedDateUtc"][:-1], "%Y-%m-%d %H:%M:%S.%f"
                        )

                    objects_to_commit.append(stop_feature)
                    progress.update(task, advance=1)

                session.add_all(objects_to_commit)
                await session.commit()

        return {
            "total_stops": len(self.stops["features"]),
            "total_poles": len(self.poles["features"]),
            "total_shelters": len(self.shelters["features"]),
            "total_rtpis": len(self.rtpis["features"]),
            "total_added_to_database": len(objects_to_commit),
        }
