import { Link } from "react-router-dom";
import { ArrowLeftIcon } from "lucide-react";
import { Navbar, Footer } from "../components/layout";
import { Omnichannel } from "../components/features";
import { CTA } from "../components/cta";
import { Container } from "../components/ui";

export function ChannelsPage() {
  return (
    <div className="min-h-screen w-full bg-canvas font-sans text-ink">
      <Navbar />
      <main className="pt-28">
        <Container>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-soft transition-colors hover:text-teal-600">

            <ArrowLeftIcon className="h-4 w-4" />
            Back to home
          </Link>
        </Container>
        <Omnichannel />
        <CTA />
      </main>
      <Footer />
    </div>);

}
