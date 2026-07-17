"""
Multi-Rail Payout Router
Intelligent routing and failover across payment providers.
Single configuration flag switches between Airwallex, Nium, Wise, or on-chain.
"""

import logging
from typing import Dict, Any, Optional, List
from enum import Enum

from .payout_adapter import (
    PayoutProviderAdapter,
    PayoutRail,
    PayoutStatus,
    PayoutResult,
    PayoutProviderError
)
from .compliance_packet import CompliancePacketGenerator, CompliancePacket, CompliancePayload

logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    """Routing strategy for selecting payment rail"""
    PRIMARY_ONLY = "primary_only"  # Use primary rail, fail if unavailable
    FAILOVER = "failover"  # Try primary, fallback to secondary
    LOWEST_COST = "lowest_cost"  # Route to cheapest rail
    FASTEST = "fastest"  # Route to fastest rail
    ROUND_ROBIN = "round_robin"  # Distribute across rails


class PayoutRouter:
    """
    Intelligent multi-rail payment router.
    
    Key Features:
    - Zero-config provider switching (flip one flag)
    - Automatic failover on provider downtime
    - Cost optimization routing
    - Health monitoring and circuit breaking
    
    Usage:
        router = PayoutRouter(config)
        result = await router.execute_payout(
            amount=1000,
            currency="USD",
            destination="beneficiary_123",
            provider_data=compliance_payload
        )
    """
    
    def __init__(
        self,
        primary_rail: PayoutRail,
        adapters: Dict[PayoutRail, PayoutProviderAdapter],
        compliance_generator: CompliancePacketGenerator,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize payment router.
        
        Args:
            primary_rail: Default rail to use
            adapters: Dict of PayoutRail -> Provider adapter
            compliance_generator: Generator for compliance packets
            config: Router configuration including:
                - routing_strategy: RoutingStrategy enum
                - failover_rails: List of fallback rails in order
                - max_retries: Max retry attempts per rail
                - circuit_breaker_threshold: Failure count to open circuit
        """
        self.primary_rail = primary_rail
        self.adapters = adapters
        self.compliance_generator = compliance_generator
        self.config = config or {}
        
        self.routing_strategy = RoutingStrategy(
            self.config.get('routing_strategy', 'primary_only')
        )
        self.failover_rails = self.config.get('failover_rails', [])
        self.max_retries = self.config.get('max_retries', 3)
        
        # Circuit breaker state
        self._circuit_failures: Dict[PayoutRail, int] = {}
        self._circuit_open: Dict[PayoutRail, bool] = {}
        self._circuit_threshold = self.config.get('circuit_breaker_threshold', 5)
        
        # Round-robin counter
        self._round_robin_index = 0
        
        logger.info(
            f"PayoutRouter initialized: primary={primary_rail.value}, "
            f"strategy={self.routing_strategy.value}, "
            f"adapters={list(adapters.keys())}"
        )
    
    def _is_circuit_open(self, rail: PayoutRail) -> bool:
        """Check if circuit breaker is open for a rail"""
        return self._circuit_open.get(rail, False)
    
    def _record_success(self, rail: PayoutRail):
        """Record successful transaction (close circuit if needed)"""
        self._circuit_failures[rail] = 0
        if self._circuit_open.get(rail, False):
            logger.info(f"Circuit closed for {rail.value}")
            self._circuit_open[rail] = False
    
    def _record_failure(self, rail: PayoutRail):
        """Record failed transaction (open circuit if threshold reached)"""
        failures = self._circuit_failures.get(rail, 0) + 1
        self._circuit_failures[rail] = failures
        
        if failures >= self._circuit_threshold:
            logger.warning(
                f"Circuit opened for {rail.value} after {failures} failures"
            )
            self._circuit_open[rail] = True
    
    def _select_rail(
        self,
        amount: float,
        currency: str,
        available_rails: Optional[List[PayoutRail]] = None
    ) -> PayoutRail:
        """
        Select optimal rail based on routing strategy.
        
        Args:
            amount: Transaction amount
            currency: Currency code
            available_rails: Optional list of rails to choose from
            
        Returns:
            Selected PayoutRail
        """
        if available_rails is None:
            available_rails = [
                rail for rail in self.adapters.keys()
                if not self._is_circuit_open(rail)
            ]
        
        if not available_rails:
            raise PayoutProviderError("No available payment rails")
        
        if self.routing_strategy == RoutingStrategy.PRIMARY_ONLY:
            if self.primary_rail in available_rails:
                return self.primary_rail
            raise PayoutProviderError(f"Primary rail {self.primary_rail.value} unavailable")
        
        elif self.routing_strategy == RoutingStrategy.FAILOVER:
            # Try primary first
            if self.primary_rail in available_rails:
                return self.primary_rail
            # Fallback to first available failover rail
            for rail in self.failover_rails:
                if rail in available_rails:
                    return rail
            # Use any available rail
            return available_rails[0]
        
        elif self.routing_strategy == RoutingStrategy.ROUND_ROBIN:
            # Rotate through available rails
            rail = available_rails[self._round_robin_index % len(available_rails)]
            self._round_robin_index += 1
            return rail
        
        elif self.routing_strategy == RoutingStrategy.LOWEST_COST:
            # TODO: Implement cost comparison logic
            # For now, fallback to primary
            return self.primary_rail if self.primary_rail in available_rails else available_rails[0]
        
        elif self.routing_strategy == RoutingStrategy.FASTEST:
            # TODO: Implement latency-based routing
            # For now, fallback to primary
            return self.primary_rail if self.primary_rail in available_rails else available_rails[0]
        
        return self.primary_rail
    
    async def execute_payout(
        self,
        amount: float,
        currency: str,
        destination: str,
        provider_data: CompliancePayload,
        recipient_bank_id: str,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PayoutResult:
        """
        Execute payout with automatic routing and failover.
        
        Args:
            amount: Transfer amount
            currency: ISO currency code
            destination: Beneficiary account identifier
            provider_data: Raw compliance data for packet generation
            recipient_bank_id: Bank ID for compliance packet encryption
            idempotency_key: Optional idempotency key
            metadata: Optional transaction metadata
            
        Returns:
            PayoutResult with transaction details
        """
        import uuid
        if idempotency_key is None:
            idempotency_key = str(uuid.uuid4())
        
        # Generate compliance packet
        compliance_packet = self.compliance_generator.generate_packet(
            payload=provider_data,
            recipient_id=recipient_bank_id,
            verification_method="OFAC_API_v1"
        )
        
        # Serialize packet for transmission
        packet_str = self.compliance_generator.serialize_packet(compliance_packet)
        
        # Select rail(s) to try
        available_rails = [
            rail for rail in self.adapters.keys()
            if not self._is_circuit_open(rail)
        ]
        
        if not available_rails:
            logger.error("All payment rails unavailable (circuits open)")
            raise PayoutProviderError("All payment rails are currently unavailable")
        
        # Primary attempt
        primary_rail = self._select_rail(amount, currency, available_rails)
        adapter = self.adapters[primary_rail]
        
        logger.info(
            f"Executing payout: amount={amount} {currency}, "
            f"rail={primary_rail.value}, idempotency={idempotency_key}"
        )
        
        try:
            result = await adapter.execute_payout(
                amount=amount,
                currency=currency,
                destination=destination,
                compliance_packet=packet_str,
                idempotency_key=idempotency_key,
                metadata=metadata
            )
            
            if result.success:
                self._record_success(primary_rail)
                logger.info(
                    f"Payout successful: {result.transaction_id} via {primary_rail.value}"
                )
                return result
            else:
                self._record_failure(primary_rail)
                logger.warning(
                    f"Payout failed on {primary_rail.value}: {result.error_message}"
                )
                
                # Attempt failover if strategy allows
                if self.routing_strategy == RoutingStrategy.FAILOVER:
                    return await self._attempt_failover(
                        amount, currency, destination, packet_str,
                        idempotency_key, metadata, attempted_rails=[primary_rail]
                    )
                
                return result
                
        except PayoutProviderError as e:
            self._record_failure(primary_rail)
            logger.error(
                f"Provider error on {primary_rail.value}: {e}",
                exc_info=True
            )
            
            # Attempt failover if strategy allows
            if self.routing_strategy == RoutingStrategy.FAILOVER:
                return await self._attempt_failover(
                    amount, currency, destination, packet_str,
                    idempotency_key, metadata, attempted_rails=[primary_rail]
                )
            
            raise
    
    async def _attempt_failover(
        self,
        amount: float,
        currency: str,
        destination: str,
        compliance_packet: str,
        idempotency_key: str,
        metadata: Optional[Dict[str, Any]],
        attempted_rails: List[PayoutRail]
    ) -> PayoutResult:
        """
        Attempt failover to backup rails.
        """
        available_rails = [
            rail for rail in self.adapters.keys()
            if rail not in attempted_rails and not self._is_circuit_open(rail)
        ]
        
        if not available_rails:
            logger.error("No failover rails available")
            return PayoutResult(
                success=False,
                transaction_id=idempotency_key,
                rail=attempted_rails[0],
                status=PayoutStatus.FAILED,
                amount=amount,
                currency=currency,
                destination=destination,
                compliance_verified=False,
                error_code="NO_FAILOVER",
                error_message="All payment rails exhausted"
            )
        
        # Try next available rail
        failover_rail = available_rails[0]
        adapter = self.adapters[failover_rail]
        
        logger.info(f"Attempting failover to {failover_rail.value}")
        
        try:
            result = await adapter.execute_payout(
                amount=amount,
                currency=currency,
                destination=destination,
                compliance_packet=compliance_packet,
                idempotency_key=f"{idempotency_key}-failover",
                metadata=metadata
            )
            
            if result.success:
                self._record_success(failover_rail)
                logger.info(f"Failover successful via {failover_rail.value}")
                return result
            else:
                self._record_failure(failover_rail)
                # Try next rail if available
                if len(available_rails) > 1:
                    return await self._attempt_failover(
                        amount, currency, destination, compliance_packet,
                        idempotency_key, metadata,
                        attempted_rails=attempted_rails + [failover_rail]
                    )
                return result
                
        except PayoutProviderError as e:
            self._record_failure(failover_rail)
            logger.error(f"Failover failed on {failover_rail.value}: {e}")
            
            # Try next rail if available
            if len(available_rails) > 1:
                return await self._attempt_failover(
                    amount, currency, destination, compliance_packet,
                    idempotency_key, metadata,
                    attempted_rails=attempted_rails + [failover_rail]
                )
            
            raise
    
    async def check_payout_status(
        self,
        transaction_id: str,
        rail: Optional[PayoutRail] = None
    ) -> PayoutResult:
        """Check status of existing payout"""
        if rail is None:
            rail = self.primary_rail
        
        adapter = self.adapters[rail]
        return await adapter.check_payout_status(transaction_id)
    
    async def health_check_all_rails(self) -> Dict[PayoutRail, bool]:
        """
        Check health of all configured payment rails.
        
        Returns:
            Dict of rail -> health status
        """
        results = {}
        for rail, adapter in self.adapters.items():
            try:
                healthy = await adapter.health_check()
                results[rail] = healthy
            except Exception as e:
                logger.error(f"Health check failed for {rail.value}: {e}")
                results[rail] = False
        
        return results
