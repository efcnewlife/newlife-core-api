"""
Facility admin API router aggregate.
"""
from portal.routers.auth_router import AuthRouter
from .room import router as room_router
from .room_slot_template import router as room_slot_template_router
from .rental_rate import router as rental_rate_router
from .rental_catalog import router as rental_catalog_router
from .booking import router as booking_router
from .member import router as member_router
from .override_log import router as override_log_router

router = AuthRouter(is_admin=True)
router.include_router(room_router, prefix="/rooms", tags=["Facility Room"])
router.include_router(room_slot_template_router, prefix="/room-slot-templates", tags=["Facility Room Slot Template"])
router.include_router(rental_rate_router, prefix="/rental-rates", tags=["Facility Rental Rate"])
router.include_router(rental_catalog_router, tags=["Facility Rental Catalog"])
router.include_router(booking_router, prefix="/bookings", tags=["Facility Booking"])
router.include_router(member_router, prefix="/members", tags=["Facility Member"])
router.include_router(override_log_router, prefix="/booking-override-logs", tags=["Facility Override Log"])
