fn main() {
    if std::env::args().any(|arg| arg == "--check") {
        frankengate_analytics_control::contract_self_check()
            .expect("analytics control-plane contract self-check failed");
        println!(
            "FrankenGate analytics contract v{}: OK",
            frankengate_analytics_control::PROTOCOL_VERSION
        );
    } else {
        println!("FrankenGate analytics control-plane contract slice");
        println!("Run with --check to validate the leased-job protocol.");
    }
}
