import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 text-center">
      <p className="text-lg font-medium">Page not found</p>
      <Link to="/" className="text-sm text-blue-600">
        Back to dashboard
      </Link>
    </div>
  );
}
