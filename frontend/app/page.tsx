import { redirect } from "next/navigation";

// Root → overview dashboard (auth check handled by dashboard layout)
export default function Root() {
  redirect("/overview");
}
